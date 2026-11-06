# Hosted dataset selection

Render's build validates and ships four packs: `demo-6` (6 hosts),
`synth-enterprise-30` (30), `synth-enterprise-120` (120), and
`synth-enterprise-300` (300). Their validated payloads total 2,708,112 bytes
(2.59 MiB): 186,683 bytes, 373,250 bytes, 779,819 bytes, and 1,368,360 bytes
respectively. `synth-datacenter-300` (1,365,457 bytes) remains in the repository for
local use and is removed only from Render's clean build checkout by
`deploy/prepare_hosted_packs.py`. Registry metadata still marks it unavailable on the
host. The selection is based on coverage of the six-host demo, two small enterprise
workspaces, and the larger scale fixture; shipped packs are validated and each is
limited to 25 MiB.

The Render service remains one Gunicorn worker with four request threads because live
world state is in memory. Uploads are limited to 50 MiB on Render and derived packs to
25 MiB. The current `web/dist` contains 55 files / 2,446,717 bytes; JavaScript totals
2,080,437 bytes (602,169 bytes gzip). The entry chunk is 218,229 bytes (68,626 gzip).
The 3D scene and Three.js are lazy chunks of 818,163 and 586,410 bytes, respectively.
The 100,000-event pipeline memory probe passed; its pytest process peaked at
223.2 MiB working set on this Windows/Python 3.11 environment, below 512 MiB. This is a
local measurement, not a Render measurement. The hosted service uses ephemeral storage;
user uploads and replay data are not durable across restarts. Rebuild and verify a hosted deployment with
`python lead-core/integration/check_hosted.py <service-url> <admin-password>`.
