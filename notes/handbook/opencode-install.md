# Opencode Install

This document provides instructions for installing Opencode with the intent of authenticating with GitHub Enterprise. Please note that due to a bug in the latest versions, we need to use Opencode version 1.1.9 and disable auto-updates.

Tags: #handbook #opencode #ai
Links:

---

## Table of Contents

<!-- toc -->

- [Installation](#installation)
- [Surprise](#surprise)
- [Easter](#easter)
- [References](#references)

<!-- tocstop -->

---

## Installation

> [!IMPORTANT]
> Due to a bug in the latest versions, we need to use Opencode version 1.1.9, login to BMW's GitHub Enterprise and then update

```sh

npm install -g opencode-ai@1.1.9

export OPENCODE_DISABLE_AUTOUPDATE=true

opencode auth login

  ┌  Add credential
  │
  ◇  Select provider
  │  GitHub Copilot
  │
  ◇  Select GitHub deployment type
  │  GitHub Enterprise
  │
  ◇  Enter your GitHub Enterprise URL or domain
  │  bmw.ghe.com
  │
  ●  Go to: https://bmw.ghe.com/login/device
  │
  ●  Enter code: <CODE>
  │
  ◇  Login successful
  │
  └  Done

```

After that, you can open a new shell session and run `opencode` to auto-upgrade.

## Surprise

Opencode is now fixed and discontinued.

## Easter

This is about easter eggs

---

## References

- [Github-Copilot-Requirements](https://atc.bmwgroup.net/confluence/spaces/AOS/pages/4309231404/Your+GitHub+Copilot+experience)
- [opencode-issue](https://github.com/anomalyco/opencode/issues/3936)

---
