import asyncio
import uuid
import time
import json
from dataclasses import dataclass, field
from typing import Optional
from loguru import logger
from core.events import event_bus

TOKEN_LIMIT_PER_SESSION = 50_000


@dataclass
class CallSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    call_id: str = ""
    channel: str = ""
    caller_id: str = ""
    source: str = "unknown"
    user_id: Optional[int] = None
    started_at: float = field(default_factory=time.time)
    active: bool = True
    gemini_session: Optional[object] = None
    audio_queue_in: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=500))
    audio_queue_out: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=500))
    metadata: dict = field(default_factory=dict)
    tokens_input: int = 0
    tokens_output: int = 0

    @property
    def tokens_total(self) -> int:
        return self.tokens_input + self.tokens_output

    @property
    def token_limit_reached(self) -> bool:
        return self.tokens_total >= TOKEN_LIMIT_PER_SESSION

    @property
    def duration(self) -> float:
        return time.time() - self.started_at

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name in ("active", "tokens_input", "tokens_output", "call_id", "channel", "caller_id", "metadata"):
            if hasattr(self, "session_id"):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.sync_to_redis())
                except RuntimeError:
                    pass

    async def sync_to_redis(self):
        from django_project import state
        if state.redis_client is None:
            return
        try:
            mapping = {
                "session_id": self.session_id,
                "call_id": self.call_id or "",
                "channel": self.channel or "",
                "caller_id": self.caller_id or "",
                "source": self.source or "unknown",
                "user_id": str(self.user_id) if self.user_id is not None else "",
                "started_at": str(self.started_at),
                "active": "1" if self.active else "0",
                "tokens_input": str(self.tokens_input),
                "tokens_output": str(self.tokens_output),
                "metadata": json.dumps(self.metadata or {}),
            }
            await state.redis_client.hset(f"session:{self.session_id}", mapping=mapping)
            await state.redis_client.expire(f"session:{self.session_id}", 3600)

            if self.active:
                await state.redis_client.sadd("active_sessions", self.session_id)
            else:
                await state.redis_client.srem("active_sessions", self.session_id)
        except Exception as e:
            logger.error(f"Error sincronizando sesión {self.session_id} a Redis: {e}")


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, CallSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(self, source: str = "unknown", user_id: int | None = None, **kwargs) -> CallSession:
        if source == "web":
            active_sess = await self.get_active_sessions()
            duplicate_ids = [
                s_id for s_id, s in active_sess.items()
                if s.source == "web" and s.active and s.user_id == user_id
            ]
            for old_id in duplicate_ids:
                logger.info(f"Cerrando sesión web duplicada para user_id={user_id}: {old_id}")
                await event_bus.emit("session_kill_request", session_id=old_id)
                await self.end_session(old_id, reason="new_session_override")

        session = CallSession(source=source, user_id=user_id, **kwargs)
        async with self._lock:
            self._sessions[session.session_id] = session
        logger.info(f"Sesión creada: {session.session_id} (fuente: {source}, user_id: {user_id})")
        await session.sync_to_redis()
        await event_bus.emit("session_created", session=session)
        return session

    async def get_session(self, session_id: str) -> Optional[CallSession]:
        session = self._sessions.get(session_id)
        if session:
            return session

        from django_project import state
        if state.redis_client is not None:
            try:
                data = await state.redis_client.hgetall(f"session:{session_id}")
                if data:
                    active_bool = data.get("active") == "1"
                    user_id_str = data.get("user_id")
                    user_id_val = int(user_id_str) if user_id_str else None
                    started_at_val = float(data.get("started_at", time.time()))
                    metadata_val = {}
                    if data.get("metadata"):
                        try:
                            metadata_val = json.loads(data.get("metadata"))
                        except Exception:
                            pass

                    session = CallSession(
                        session_id=data.get("session_id", session_id),
                        call_id=data.get("call_id", ""),
                        channel=data.get("channel", ""),
                        caller_id=data.get("caller_id", ""),
                        source=data.get("source", "unknown"),
                        user_id=user_id_val,
                        started_at=started_at_val,
                        active=active_bool,
                        tokens_input=int(data.get("tokens_input", "0")),
                        tokens_output=int(data.get("tokens_output", "0")),
                        metadata=metadata_val
                    )
                    return session
            except Exception as e:
                logger.error(f"Error recuperando sesión {session_id} desde Redis: {e}")
        return None

    async def end_session(self, session_id: str, reason: str = "normal"):
        async with self._lock:
            session = self._sessions.pop(session_id, None)

        if not session:
            session = await self.get_session(session_id)

        if session:
            session.active = False
            await session.sync_to_redis()
            logger.info(f"Sesión terminada: {session_id} ({reason}) - Duración: {session.duration:.1f}s")
            await event_bus.emit("session_ended", session=session, reason=reason)
        return session

    async def get_active_sessions(self) -> dict[str, CallSession]:
        from django_project import state
        if state.redis_client is None:
            return self.active_sessions

        active_dict = {}
        try:
            session_ids = await state.redis_client.smembers("active_sessions")
            for s_id in session_ids:
                if s_id in self._sessions:
                    active_dict[s_id] = self._sessions[s_id]
                else:
                    s = await self.get_session(s_id)
                    if s:
                        active_dict[s_id] = s
        except Exception as e:
            logger.error(f"Error obteniendo sesiones activas desde Redis: {e}")
            return self.active_sessions

        return active_dict

    @property
    def active_sessions(self) -> dict[str, CallSession]:
        return {k: v for k, v in self._sessions.items() if v.active}

    @property
    def count(self) -> int:
        return len(self.active_sessions)
