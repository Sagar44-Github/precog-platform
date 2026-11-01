"""VIZ's backend package: simulated containment with re-evaluation, and push notifications.

register(ctx) plugs two hooks into the backend:

    containment = ctx.hooks.get("containment")
    containment.propose(world, target_host, forecast_id, requested_by) -> containment_action (pending_confirmation)
    containment.confirm(world, action_id)                              -> containment_action (executed)
    containment.cancel(world, action_id)                               -> containment_action (cancelled)

    push = ctx.hooks.get("push")
    push.register(token)

Settings (environment variables): CONTAINMENT_CONFIRM_SECONDS (default 60); FCM_PROJECT_ID plus FCM_CREDENTIALS_FILE or
FCM_CREDENTIALS_JSON switch real Firebase sending on; PUSH_WATCHER=0 switches the alert watcher off.
"""
import logging
import os

from .containment import ContainmentService
from .push import AlertWatcher, FcmSender, LogSender, PushHook, alert_notification, build_sender_from_env

log = logging.getLogger("precog.viz")

__all__ = ["register", "ContainmentService", "AlertWatcher", "FcmSender", "LogSender", "PushHook", "alert_notification", "build_sender_from_env"]


def register(ctx):
    seconds = float(os.environ.get("CONTAINMENT_CONFIRM_SECONDS", "60"))
    ctx.hooks.register("containment", ContainmentService(ctx.world, ctx.hooks, confirm_seconds=seconds, contracts=ctx.contracts))
    ctx.hooks.register("push", PushHook(ctx.world))
    if os.environ.get("PUSH_WATCHER", "1").strip().lower() not in ("0", "false", "no", "off"):
        AlertWatcher(ctx.world, build_sender_from_env(os.environ)).start()
    log.info("Containment ready (confirm within %s s)", seconds)
