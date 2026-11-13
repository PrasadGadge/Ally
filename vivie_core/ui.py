"""WebSocket UI bridge — single update path."""

from vivie_core.log_util import warn


def update_ui(signal_name: str, *args) -> None:
    try:
        from Vivie_UI import emit_to_ui

        if signal_name == "sig_memory_update":
            if len(args) >= 2 and not isinstance(args[0], dict):
                emit_to_ui(signal_name, {"episodes": args[0], "knowledge": args[1]})
                return
            if len(args) == 1 and isinstance(args[0], dict):
                emit_to_ui(signal_name, args[0])
                return
            if len(args) >= 2:
                emit_to_ui(signal_name, {"episodes": args[0], "knowledge": args[1]})
                return

        value = args[0] if args else None
        emit_to_ui(signal_name, value)
    except Exception as exc:
        warn(f"UI emit failed ({signal_name})", exc)


def emit_memory_counts() -> None:
    try:
        from memory_core.episodic_memory import get_episode_count
        from knowledge_core.chroma_manager import get_chroma_manager

        update_ui(
            "sig_memory_update",
            {"episodes": get_episode_count(), "knowledge": get_chroma_manager().count()},
        )
    except Exception as exc:
        warn("emit_memory_counts", exc)
