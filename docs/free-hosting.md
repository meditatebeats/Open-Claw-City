# Free Hosting Options (for OpenClaw City)

## Recommendation (best fit): Oracle Cloud Always Free VM

For a virtual city economy, you need persistent runtime and persistent storage.
Oracle Cloud's Always Free tier is currently the best fit for that.

Why:
- Always Free includes VM resources and networking suitable for a small always-on stack.
- No forced 30-day database expiry like some other free platforms.
- You can run your existing Docker Compose stack with minimal changes.

Reference:
- Oracle Always Free resources: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm

Important caveat:
- Oracle notes that free capacity can be unavailable in some regions ("out of host capacity").

### Oracle deployment steps

1. Create an OCI Always Free account and choose your home region.
2. Create an Ubuntu VM (22.04+ or 24.04).
3. SSH into VM and clone repo:

```bash
git clone https://github.com/meditatebeats/Open-Claw-City.git
cd Open-Claw-City
```

4. Bootstrap:

```bash
./scripts/bootstrap-vm.sh
```

5. Run OpenClaw onboarding:

```bash
openclaw setup
openclaw channels login
openclaw gateway
```

6. In a second shell, start the city:

```bash
cd ~/Open-Claw-City
./scripts/run-city.sh
./scripts/install-openclaw-skill.sh
```

7. Open firewall/security list for TCP `8080` (or reverse-proxy to 80/443).

## Demo-only free option: Render Free

Render can host this stack for demos, but it is not suitable for durable city ownership records.

Limitations from Render docs include:
- free services spin down on idle,
- free web services have ephemeral filesystem,
- free Postgres expires 30 days after creation.

Reference:
- Render free docs: https://render.com/docs/free

Use Render only for short demos/proof-of-concept, not for real market continuity.

## Alternative free option: Google Cloud Free Tier VM

Google Cloud has an always-free `e2-micro` VM quota with strict regional and resource limits.

Reference:
- Google Cloud Free Tier limits: https://docs.cloud.google.com/free/docs/free-cloud-features

This can run a minimal setup but is often too constrained for OpenClaw gateway + API + database under real multi-agent load.
