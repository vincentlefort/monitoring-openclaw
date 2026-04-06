# Monitoring OpenClaw

Dashboard de monitoring pour l'infrastructure OpenClaw de Vincent Lefort.

## Fonctionnalités

- 📊 **Statut des services** : Bot Trading V5, Gateway OpenClaw, Crypto Confirm Bot
- 💰 **Performance financière** : PnL du jour, capital actuel
- 📈 **Derniers trades** : Tableau des trades récents avec PnL
- 🚀 **Graphique d'évolution** : Visualisation du capital sur 24h

## Structure des données

Le dashboard utilise deux sources de données :

1. **`bot_status_v5.json`** - Statut du bot trading
   ```json
   {
     "timestamp": "2026-04-06T20:20:43.566910",
     "running": true,
     "scan_count": 70,
     "positions_count": 0,
     "daily_pnl": 0.0,
     "capital": 3610.92676652
   }
   ```

2. **`trades_v5.csv`** - Historique des trades
   - Format CSV avec colonnes : id, timestamp, symbol, direction, entry_price, exit_price, pnl_usdc, pnl_pct

## Déploiement

### Sur Vercel

1. **Prérequis** :
   - Token Vercel (`VERCEL_TOKEN`) disponible dans l'environnement
   - Compte Vercel connecté

2. **Déploiement automatique** :
   ```bash
   # Installer Vercel CLI
   npm i -g vercel

   # Se connecter
   vercel login

   # Déployer
   vercel --prod
   ```

3. **Variables d'environnement** :
   - `VERCEL_TOKEN` : Token d'authentification Vercel
   - (Optionnel) `API_URL` : URL de l'API pour les données en temps réel

### Développement local

```bash
# Servir le site localement
python3 -m http.server 8080
# ou
npx serve .
```

Accéder à : http://localhost:8080

## Technologies utilisées

- **HTML5** + **CSS3** (Tailwind CSS)
- **JavaScript** (ES6)
- **Chart.js** pour les graphiques
- **Vercel** pour l'hébergement

## Auteur

Vincent Lefort – Entrepreneur & Trader Crypto basé à Munich

## Licence

Usage privé – Non destiné à la redistribution.