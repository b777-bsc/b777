# B777 Protocol (MVP) 

An on-chain settlement layer for gaming/gambling frontends to accept ERC20 payments,
automatically split revenue, and keep auditable logs.

## Features
- ERC20 payment entry (`payERC20`)
- Configurable split: developer / protocol fee / jackpot / treasury / burn
- Events for analytics and dashboards
- Minimal browser SDK and HTML demo

## Local Development
```bash
npm install
npm run node                 # start local hardhat chain
# (open another terminal)
npm run deploy               # deploy MockUSDT + B777Settlement
npm run demo                 # run a demo payment tx
```

## Using the Web Demo
1. After deployment, copy the printed contract addresses:
   - `MockUSDT`
   - `B777Settlement`
2. Open `web/index.html` in your browser.
3. Paste addresses and click **Connect Wallet** then **Pay 1 USDT** (on Hardhat network).

## Notes
- Percentages are set in basis points (sum must equal `10_000`).
- Replace `MockUSDT` with a real stablecoin on testnet/mainnet when going live.
- Extend with jackpot distribution and game logic as needed.
