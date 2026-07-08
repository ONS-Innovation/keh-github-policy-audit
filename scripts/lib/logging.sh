#!/bin/sh

LOG_CONTEXT="${LOG_CONTEXT:-BUILD}"
_LOG_CLEANUP_CMD=""

log_info() {
	printf '[INFO] [%s] %s\n' "$LOG_CONTEXT" "$*"
}

log_step() {
	printf '\n[STEP] [%s] %s\n' "$LOG_CONTEXT" "$*"
}

log_done() {
	printf '\n[DONE] [%s] %s\n' "$LOG_CONTEXT" "$*"
}

log_error() {
	printf '[ERROR] [%s] %s\n' "$LOG_CONTEXT" "$*" >&2
}

_log_on_exit() {
	exit_code=$?

	if [ "$exit_code" -ne 0 ]; then
		log_error "Script failed with exit code $exit_code"
		if [ -n "$_LOG_CLEANUP_CMD" ]; then
			log_info "Running failure cleanup"
			eval "$_LOG_CLEANUP_CMD"
		fi
	fi
}

setup_error_trap() {
	_LOG_CLEANUP_CMD="$1"
	trap '_log_on_exit' EXIT
}

clear_error_trap() {
	trap - EXIT
	_LOG_CLEANUP_CMD=""
}