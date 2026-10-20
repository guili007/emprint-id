"""
SIGAConnector — client HTTP pour l'API REST de SIGA-RDC.

SIGA utilise SessionAuthentication (cookie de session), pas JWT.
Ce connecteur :
  1. Se connecte avec un compte service (SIGA_SERVICE_USER / _PASSWORD)
  2. Conserve le cookie de session pour les appels suivants
  3. Expose des méthodes de lecture utilisées par la commande `sync_siga`

Variables d'environnement requises :
  SIGA_BASE_URL       : ex. "http://localhost:8001"
  SIGA_SERVICE_USER   : username du compte service SIGA
  SIGA_SERVICE_PASSWORD : mot de passe du compte service SIGA

Ce connecteur est utilisé SEULEMENT par la commande management `sync_siga`.
Les vues Foundry Gov lisent le cache local (GovEmployee, etc.), jamais SIGA
directement — ce qui rend Foundry resilient si SIGA est momentanément down.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger('emprint.foundry.gov')

# Timeout par appel HTTP en secondes
_TIMEOUT = 10


class SIGAConnectionError(Exception):
    """Levée quand la connexion ou l'authentification à SIGA échoue."""


class SIGAConnector:
    """
    Client HTTP session-based vers l'API SIGA-RDC.

    Usage :
        connector = SIGAConnector()
        connector.authenticate()   # POST /api/v1/auth/connexion/
        agents = connector.list_agents()
        events = connector.get_agent_events(siga_uuid)
    """

    def __init__(self):
        self.base_url = getattr(settings, 'SIGA_BASE_URL', '').rstrip('/')
        self.username = getattr(settings, 'SIGA_SERVICE_USER', '')
        self.password = getattr(settings, 'SIGA_SERVICE_PASSWORD', '')

        # requests.Session conserve le cookie CSRF + session entre les appels
        self._session = requests.Session()
        self._authenticated = False

    def authenticate(self):
        """
        Ouvre une session SIGA avec le compte service.

        SIGA exige un token CSRF (Django par défaut). On fait d'abord un GET
        sur la page de connexion pour récupérer le cookie csrftoken, puis
        on POSTe les credentials avec ce token dans l'en-tête X-CSRFToken.
        """
        if not self.base_url:
            raise SIGAConnectionError("SIGA_BASE_URL non configuré.")

        # 1. Récupérer le cookie csrftoken
        try:
            self._session.get(f"{self.base_url}/api/v1/auth/connexion/", timeout=_TIMEOUT)
        except requests.RequestException as exc:
            logger.error("Impossible d'atteindre SIGA : %s", exc, exc_info=True)
            raise SIGAConnectionError(f"SIGA injoignable : {exc}") from exc

        csrf_token = self._session.cookies.get('csrftoken', '')

        # 2. POST les credentials
        try:
            resp = self._session.post(
                f"{self.base_url}/api/v1/auth/connexion/",
                json={'username': self.username, 'password': self.password},
                headers={'X-CSRFToken': csrf_token},
                timeout=_TIMEOUT,
            )
        except requests.RequestException as exc:
            logger.error("Erreur lors de la connexion à SIGA : %s", exc, exc_info=True)
            raise SIGAConnectionError(f"Erreur connexion SIGA : {exc}") from exc

        if resp.status_code not in (200, 201):
            raise SIGAConnectionError(
                f"Authentification SIGA échouée (HTTP {resp.status_code})."
            )

        self._authenticated = True
        logger.info("Connecté à SIGA en tant que '%s'.", self.username)

    def _get(self, path, params=None):
        """GET authentifié vers l'API SIGA. Lève SIGAConnectionError si échec."""
        if not self._authenticated:
            self.authenticate()

        try:
            resp = self._session.get(
                f"{self.base_url}{path}",
                params=params,
                timeout=_TIMEOUT,
            )
        except requests.RequestException as exc:
            logger.error("Erreur GET SIGA %s : %s", path, exc, exc_info=True)
            raise SIGAConnectionError(f"Erreur GET {path} : {exc}") from exc

        resp.raise_for_status()
        return resp.json()

    def list_agents(self, page=1):
        """
        Retourne une page d'agents depuis GET /api/v1/agents/.

        Réponse DRF paginée : {'count': N, 'next': '...', 'results': [...]}
        """
        return self._get('/api/v1/agents/', params={'page': page})

    def get_agent_events(self, siga_uuid):
        """
        Retourne les événements de carrière d'un agent.
        GET /api/v1/agents/<uuid>/evenements/
        """
        return self._get(f'/api/v1/agents/{siga_uuid}/evenements/')

    def get_stats(self):
        """Statistiques agrégées. GET /api/v1/statistiques/"""
        return self._get('/api/v1/statistiques/')
