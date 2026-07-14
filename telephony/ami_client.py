from loguru import logger
from config.settings import get_settings


class AMIClient:
    """
    Cliente AMI (Asterisk Manager Interface).
    En producción usa panoramisk para conexión real.
    Actualmente opera en modo simulación.
    """

    def __init__(self):
        settings = get_settings()
        self.host = settings.ami_host
        self.port = settings.ami_port
        self.username = settings.ami_username
        self.secret = settings.ami_secret
        self._connected = False
        self._manager = None
        self.uuid_to_channel = {}

    async def connect(self):
        """Conecta al servidor AMI de Asterisk."""
        try:
            from panoramisk import Manager
            self._manager = Manager(
                host=self.host, port=self.port,
                username=self.username, secret=self.secret
            )
            
            # Registrar el manejador de eventos de variables de Asterisk
            self._manager.register_event('VarSet', self._handle_varset)
            
            await self._manager.connect()
            logger.info(f"✅ AMI Client conectado con éxito a {self.host}:{self.port}")
            self._connected = True
        except Exception as e:
            logger.error(f"❌ Error conectando a AMI: {e}. Continuando en modo simulación.")
            self._connected = False

    def _handle_varset(self, manager, event):
        """Manejador de eventos que asocia el canal de Asterisk con el UUID de la llamada."""
        var_name = event.get('Variable') or event.get('variable')
        if var_name == 'MY_UUID':
            uuid_val = (event.get('Value') or event.get('value') or "").strip()
            channel = event.get('Channel') or event.get('channel')
            if uuid_val and channel:
                self.uuid_to_channel[uuid_val] = channel
                logger.info(f"🔗 AMI: Mapeado UUID {uuid_val} al canal {channel}")

    async def disconnect(self):
        if self._manager and self._connected:
            try:
                self._manager.close()
            except Exception:
                pass
        self._connected = False
        logger.info("AMI Client desconectado")

    async def transfer(self, channel: str, extension: str, context: str = "from-extensions"):
        """
        Transfiere una llamada usando AMI Action: Redirect
        """
        if not self._connected or not self._manager:
            logger.warning("AMI no conectado, transferencia simulada")
            logger.info(f"AMI Redirect: Channel={channel} -> Exten={extension} Context={context}")
            return {"Response": "Success", "Message": f"Redirect sent (simulated) to {extension}"}

        try:
            logger.info(f"AMI Real Redirect: Channel={channel} -> Exten={extension} Context={context}")
            response = await self._manager.send_action({
                'Action': 'Redirect',
                'Channel': channel,
                'Context': context,
                'Exten': extension,
                'Priority': '1'
            })
            return response
        except Exception as e:
            logger.error(f"Error ejecutando AMI Redirect: {e}")
            return {"Response": "Error", "Message": str(e)}

    async def hangup(self, channel: str, cause: int = 16):
        """Cuelga un canal específico."""
        if not self._connected or not self._manager:
            logger.info(f"AMI Hangup: Channel={channel} Cause={cause}")
            return {"Response": "Success", "Message": f"Hangup sent (simulated) for {channel}"}

        try:
            logger.info(f"AMI Real Hangup: Channel={channel} Cause={cause}")
            response = await self._manager.send_action({
                'Action': 'Hangup',
                'Channel': channel,
                'Cause': str(cause)
            })
            return response
        except Exception as e:
            logger.error(f"Error ejecutando AMI Hangup: {e}")
            return {"Response": "Error", "Message": str(e)}

    async def originate(self, extension: str, context: str = "from-extensions",
                         caller_id: str = "Nova <*999>"):
        """Origina una nueva llamada."""
        if not self._connected or not self._manager:
            logger.info(f"AMI Originate: Exten={extension} CallerID={caller_id}")
            return {"Response": "Success", "Message": f"Originate sent (simulated) to {extension}"}

        try:
            logger.info(f"AMI Real Originate: Exten={extension} CallerID={caller_id}")
            response = await self._manager.send_action({
                'Action': 'Originate',
                'Channel': f'PJSIP/{extension}',
                'Context': context,
                'Exten': extension,
                'Priority': '1',
                'CallerID': caller_id
            })
            return response
        except Exception as e:
            logger.error(f"Error ejecutando AMI Originate: {e}")
            return {"Response": "Error", "Message": str(e)}

    @property
    def is_connected(self) -> bool:
        return self._connected
