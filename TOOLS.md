# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.

## Conway Wallet (Financial System)
Clarvis has a blockchain wallet on Base with USDC. Access via shell:

- `~/scripts/conway-wallet.sh balance` — Check USDC balance
- `~/scripts/conway-wallet.sh info` — Wallet address and config
- `~/scripts/conway-wallet.sh credits` — Conway compute credits
- `~/scripts/conway-wallet.sh status` — Full financial overview

Wallet address: 0x3f788Cf3c685996Dd07B8C04590FB7EeadbBFcAB
Network: Base (USDC)
