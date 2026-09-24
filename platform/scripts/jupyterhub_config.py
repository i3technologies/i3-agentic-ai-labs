import osfrom oauthenticator.generic import GenericOAuthenticator# ΓöÇΓöÇ Auth: Keycloak OIDC ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇc.JupyterHub.authenticator_class = GenericOAuthenticatorc.GenericOAuthenticator.client_id     = "jupyterhub"c.GenericOAuthenticator.client_secret = os.environ["KEYCLOAK_CLIENT_SECRET"]c.GenericOAuthenticator.authorize_url = (    "https://sso.i3technologies.co.ke/auth/realms/i3/protocol/openid-connect/auth")c.GenericOAuthenticator.token_url     = (    "https://sso.i3technologies.co.ke/auth/realms/i3/protocol/openid-connect/token")c.GenericOAuthenticator.userdata_url  = (    "https://sso.i3technologies.co.ke/auth/realms/i3/protocol/openid-connect/userinfo")c.GenericOAuthenticator.username_key  = "preferred_username"c.GenericOAuthenticator.scope         = ["openid", "profile", "email"]c.GenericOAuthenticator.allow_all     = True# ΓöÇΓöÇ Spawner: KubeSpawner ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇc.JupyterHub.spawner_class = "kubespawner.KubeSpawner"c.KubeSpawner.namespace       = "i3-ai-lab"c.KubeSpawner.start_timeout   = 120c.KubeSpawner.http_timeout    = 60c.KubeSpawner.image           = "quay.io/jupyter/scipy-notebook:latest"c.KubeSpawner.cpu_limit       = 2c.KubeSpawner.mem_limit       = "4G"c.KubeSpawner.cpu_guarantee   = 0.25c.KubeSpawner.mem_guarantee   = "512M"# Per-user PVCc.KubeSpawner.storage_pvc_ensure = Truec.KubeSpawner.pvc_name_template  = "jupyter-{username}"c.KubeSpawner.storage_capacity   = "5Gi"c.KubeSpawner.storage_access_modes = ["ReadWriteOnce"]# Inject AI platform env into every user notebookc.KubeSpawner.environment = {    "LITELLM_URL":   os.environ.get("LITELLM_URL",   ""),    "LITELLM_KEY":   os.environ.get("LITELLM_KEY",   ""),    "CHROMA_HOST":   os.environ.get("CHROMA_HOST",   ""),    "CHROMA_TOKEN":  os.environ.get("CHROMA_TOKEN",  ""),    "OLLAMA_URL":    "http://ollama.i3-model-gateway.svc.cluster.local:11434",    "OPENAI_API_KEY": os.environ.get("LITELLM_KEY",  ""),    "OPENAI_BASE_URL": os.environ.get("LITELLM_URL", ""),}# Pre-install AI packages in every notebook serverc.KubeSpawner.args = [    "--NotebookApp.allow_origin=*",    "--NotebookApp.token=",]# ΓöÇΓöÇ Hub settings ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇc.JupyterHub.base_url       = "/"c.JupyterHub.ip             = "0.0.0.0"c.JupyterHub.hub_ip         = "0.0.0.0"c.JupyterHub.port           = 8081# Writable data paths (PVC mounted at /srv/shared)c.JupyterHub.cookie_secret_file = "/srv/shared/jupyterhub_cookie_secret"c.JupyterHub.db_url = (    "postgresql+psycopg2://jupyterhub:{pw}@i3-postgres-pgbouncer.i3-data.svc:5432/jupyterhub_db"    .format(pw=os.environ.get("POSTGRES_PASSWORD", "")))# Proxy runs as a sidecar ΓÇö tell hub where to find the APIc.ConfigurableHTTPProxy.auth_token = os.environ["JUPYTERHUB_CRYPT_KEY"]c.ConfigurableHTTPProxy.api_url    = "http://127.0.0.1:8001"c.ConfigurableHTTPProxy.should_start = False# Crypt key for cookiesc.CryptKeeper.keys = [bytes.fromhex(os.environ["JUPYTERHUB_CRYPT_KEY"])]
    # ── Idle culler: shut down notebooks idle > 1h ───────────────
    c.JupyterHub.services = [
        {
            "name": "idle-culler",
            "admin": True,
            "command": [
                "python3", "-m", "jupyterhub_idle_culler",
                "--timeout=3600",
                "--max-age=86400",
                "--concurrency=5"
            ],
        }
    ]
    c.JupyterHub.load_roles = [
        {
            "name": "idle-culler",
            "description": "Cull idle single-user servers",
            "scopes": [
                "list:users",
                "read:users:activity",
                "read:servers",
                "delete:servers",
                "admin:users",
            ],
            "services": ["idle-culler"],
        }
    ]