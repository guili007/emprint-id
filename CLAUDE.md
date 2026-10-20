# CLAUDE.md — EmPrint-iD · Eyeshield Platform · Module 01

> Ce fichier est le brief complet pour Claude Code.
> Lis-le intégralement avant d'écrire la moindre ligne de code.
> Dernière mise à jour : 2026-10-20

---

## 1. QUI EST GUILI

- **Guili Monghiro** — Fondateur & CEO de **Kinetix Agency**, Kinshasa (Gombe), RDC
- Étudiant L2 Informatique + Kadea Academy (spécialisation IA)
- Ambassadeur officiel du programme **WE ACT** (Rawbank)
- Stack maîtrisé : React, TypeScript, Django, DRF, PostgreSQL, GSAP, Three.js, Tailwind, Claude API
- Email projet : **guili@eyeshield.org**
- Hébergement : **Hostinger** (VPS + domaine eyeshield.org)

---

## 2. VISION GLOBALE — EYESHIELD PLATFORM

Eyeshield est une **plateforme nationale d'intelligence opérationnelle** pour la RDC.
Elle unifie identité, données et intelligence de l'État congolais pour 100 millions de citoyens.

**SIGA RDC est un projet SÉPARÉ** — ne jamais mélanger les deux codebases.

### 4 modules :

| Module | Nom | Couleur | Statut |
|--------|-----|---------|--------|
| 01 | **EmPrint-iD** | `#00dfc8` teal | ✅ Sprint 1 en cours |
| 02 | Eyeshield Data | `#4a7af5` blue | Planifié 2026 |
| 03 | Eyeshield Foundry | `#f2c341` gold | Planifié 2027 |
| 04 | Eyeshield Intel | `#e03048` red | Vision 2028+ |

---

## 3. ARCHITECTURE DU PROJET (Sprint 1 — construit)

```
emprint-id/
├── backend/
│   ├── config/
│   │   ├── settings/
│   │   │   ├── base.py
│   │   │   └── development.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py          ← WebSocket (Django Channels)
│   ├── apps/
│   │   ├── citizens/        ← Modèle Citizen, QR verify v1
│   │   └── biometric/       ← Sprint 1 : face + watchlist
│   │       ├── models.py    ← CitizenFaceEmbedding, WatchlistEntry, VerificationLog
│   │       ├── services.py  ← BiometricService (DeepFace + ArcFace)
│   │       ├── views.py     ← /api/v2/ endpoints
│   │       ├── consumers.py ← WebSocket alertes silencieuses
│   │       └── exceptions.py
│   └── manage.py
└── CLAUDE.md
```

---

## 4. DÉCISIONS TECHNIQUES PRISES (NE PAS REMETTRE EN QUESTION)

### Face Recognition
- **Moteur** : DeepFace + backend ArcFace
- **anti_spoofing=True** — JAMAIS désactivé
- **Liveness AVANT reconnaissance** — ordre strict dans BiometricService.verify()

### Protocole Watchlist Hit
- **Silent Flagging** : le suspect ne sait pas qu'il est repéré
- **WebSocket silencieux** vers le dashboard sécurité via Redis pub/sub
- **Log REJECTED_WATCHLIST** avec audit trail complet
- **Liveness échoué** : log TOUJOURS (tentative de fraude potentielle)

### Vector DB
- Maintenant : **pgvector** (jusqu'à ~500K citoyens)
- Phase 2 : migration **Milvus**

### Mobile
- Maintenant : **PWA React** sur verify.eyeshield.org
- Rôles JWT : ROLE_POLICE, ROLE_BANK, ROLE_BORDER, ROLE_ADMIN, ROLE_HEALTH

---

## 5. SÉCURITÉ — RÈGLES ABSOLUES

1. Toute réponse API signée **HMAC-SHA256**
2. `anti_spoofing=True` jamais optionnel
3. **Liveness AVANT watchlist** — pas l'inverse
4. Watchlist hit = **alerte silencieuse** (suspect ne sait pas)
5. `VerificationLog` immuable — jamais de DELETE, jamais de UPDATE
6. Aucune image/embedding dans les logs
7. Erreurs techniques : log `exc_info=True` côté serveur, message générique côté client
8. Rate limiting : 10 req/min sur tous les endpoints biométriques

---

## 6. PROCHAINES ÉTAPES (Sprint 2)

1. PWA React Role-Based (POLICE, BANK, ADMIN, BORDER)
2. WebSocket alertes temps réel
3. Dashboard admin
4. Tests automatisés
5. Docker Compose complet
