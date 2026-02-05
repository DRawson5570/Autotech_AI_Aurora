#!/usr/bin/env bash
# scripts/install_ollama_model_poweredge2.sh
# Safely install a local GGUF model on a remote host (poweredge2) into Ollama's model folder (~/.ollama/models/<model>/model.gguf)
# Usage examples:
#   ./scripts/install_ollama_model_poweredge2.sh --host poweredge2 --user drawson --remote-file ~/Midnight-Miqu-70B-v1.5-Q4_K_M.gguf --model-name midnight-miqu-70b
#   ./scripts/install_ollama_model_poweredge2.sh --host poweredge2 --user drawson --remote-file /local/path/thing.gguf --model-name mymodel --scp-from-local
# Options:
#   --host           remote host (required)
#   --user           remote user (default: current user)
#   --remote-file    path to gguf on the remote machine (default: ~/model.gguf)
#   --local-file     alternative: path to a local file to scp up to remote
#   --scp-from-local copy the local file up to the remote host
#   --model-name     desired model name (used as directory name under ~/.ollama/models/) (required)
#   --install-ollama if set, run Ollama's install script on the remote host if 'ollama' is missing (NON-INTERACTIVE)
#   --force          overwrite existing model file if present
#   --port           ssh port (default 22)
#   --dry-run        show actions but don't execute changes
#   --register       create a Modelfile (FROM <model_dir>) and run 'ollama create' to register the model (may be slow)
#   --async-create   run the 'ollama create' asynchronously on the target and return immediately
#   --create-timeout <seconds>  if set, use timeout to limit the create duration (if available on the system)
#   --quantize <level>  pass '-q <level>' to 'ollama create' when registering the model
# Notes: the script tries to be conservative by default; if Ollama doesn't list the model after placing the file,
# the script will still leave the file in place and report what to run next.

set -euo pipefail

usage() {
  grep '^#' "$0" | sed 's/^#//'
  exit 1
}

# Defaults
REMOTE_USER="$(whoami)"
REMOTE_HOST=""
REMOTE_FILE="~/.local_models/model.gguf"
LOCAL_FILE=""
MODEL_NAME=""
INSTALL_OLLAMA=false
FORCE=false
SSH_PORT=22
DRY_RUN=false
SCP_FROM_LOCAL=false
LOCAL_MODE=false
SYMLINK_NAME=""
SANITY_CHECK=false
SANITY_PROMPT="Hello"
SANITY_TIMEOUT=20

# Create/Register options
REGISTER=false
CREATE_ASYNC=false
CREATE_TIMEOUT=0
QUANTIZE=""

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) REMOTE_HOST="$2"; shift 2;;
    --user) REMOTE_USER="$2"; shift 2;;
    --remote-file) REMOTE_FILE="$2"; shift 2;;
    --local-file) LOCAL_FILE="$2"; shift 2;;
    --model-name) MODEL_NAME="$2"; shift 2;;
    --install-ollama) INSTALL_OLLAMA=true; shift 1;;
    --force) FORCE=true; shift 1;;
    --port) SSH_PORT="$2"; shift 2;;
    --dry-run) DRY_RUN=true; shift 1;;
    --scp-from-local) SCP_FROM_LOCAL=true; shift 1;;
    --symlink-name) SYMLINK_NAME="$2"; shift 2;;
    --sanity-check) SANITY_CHECK=true; shift 1;;
    --sanity-prompt) SANITY_PROMPT="$2"; shift 2;;
    --sanity-timeout) SANITY_TIMEOUT="$2"; shift 2;;
    --local) LOCAL_MODE=true; shift 1;;
    --register) REGISTER=true; shift 1;;
    --async-create) CREATE_ASYNC=true; shift 1;;
    --create-timeout) CREATE_TIMEOUT="$2"; shift 2;;
    --quantize) QUANTIZE="$2"; shift 2;;
    -h|--help) usage; shift 1;;
    *) echo "Unknown arg: $1"; usage;;
  esac
done

if [[ -z "$REMOTE_HOST" ]]; then
  echo "Error: --host is required"
  usage
fi

if [[ -z "$MODEL_NAME" ]]; then
  echo "Error: --model-name is required"
  usage
fi

SSH_TARGET="${REMOTE_USER}@${REMOTE_HOST}"
REMOTE_MODEL_DIR="~/.ollama/models/${MODEL_NAME}"
REMOTE_TARGET_PATH="${REMOTE_MODEL_DIR}/model.gguf"

echo "Target: $SSH_TARGET"
echo "Model name: $MODEL_NAME"
echo "Remote model path: $REMOTE_TARGET_PATH"
if [[ "$DRY_RUN" == true ]]; then
  echo "DRY RUN: no changes will be made"
fi

SSH_OPTS=( -o BatchMode=yes -p "$SSH_PORT" )

# Helper to run remote command (prints and runs; honors dry-run)
run_remote() {
  echo "+ ssh ${SSH_TARGET} -- $*"
  if [[ "$DRY_RUN" == false ]]; then
    ssh "${SSH_TARGET}" "${SSH_OPTS[@]}" -- "$@"
  fi
}

run_local() {
  echo "+ $*"
  if [[ "$DRY_RUN" == false ]]; then
    bash -lc "$@"
  fi
}

# If copying from local, ensure local file exists and scp it first
if [[ "$SCP_FROM_LOCAL" == true ]]; then
  if [[ -z "$LOCAL_FILE" ]]; then
    echo "--scp-from-local requires --local-file"
    exit 2
  fi
  if [[ ! -f "$LOCAL_FILE" ]]; then
    echo "Local file not found: $LOCAL_FILE"
    exit 2
  fi
  if [[ "$LOCAL_MODE" == true ]]; then
    # Running locally: just use the provided local file path as the source
    echo "LOCAL MODE: using local file $LOCAL_FILE"
    REMOTE_FILE="$LOCAL_FILE"
  else
    echo "Copying local file to remote: ${LOCAL_FILE} -> ${SSH_TARGET}:~/"
    if [[ "$DRY_RUN" == false ]]; then
      scp -P "$SSH_PORT" "$LOCAL_FILE" "${SSH_TARGET}:~/"
    fi
    # After scp, set remote file path to home path
    REMOTE_FILE="~/$(basename "$LOCAL_FILE")"
  fi
fi

# Check remote file exists
echo "Checking model file: $REMOTE_FILE"
if [[ "$DRY_RUN" == false ]]; then
  if [[ "$LOCAL_MODE" == true ]]; then
    if ! bash -lc "test -f ${REMOTE_FILE}" >/dev/null 2>&1; then
      echo "Model file not found: $REMOTE_FILE"
      echo "If the file already exists under another path, pass --remote-file or use --scp-from-local"
      exit 2
    fi
  else
    if ! ssh "${SSH_TARGET}" "${SSH_OPTS[@]}" -- bash -c "\"test -f ${REMOTE_FILE} || (test -f $(printf '%q' "${REMOTE_FILE/#~/$HOME}") )\"" >/dev/null 2>&1; then
      echo "Remote model file not found: $REMOTE_FILE"
      echo "If the file already exists under another path, pass --remote-file or use --scp-from-local"
      exit 2
    fi
  fi
fi

# Optionally install ollama if missing
if [[ "$INSTALL_OLLAMA" == true ]]; then
  echo "Ensure ollama installed on remote (non-interactive)..."
  # Check ollama presence
  if [[ "$DRY_RUN" == false ]]; then
    if ! ssh "${SSH_TARGET}" "${SSH_OPTS[@]}" -- command -v ollama >/dev/null 2>&1; then
      echo "Ollama not found on remote; installing via official script..."
      # Non-interactive install script
      run_remote bash -lc "curl -fsSL https://ollama.com/install.sh | sh"
    else
      echo "Ollama already installed on remote"
    fi
  fi
fi

# Create remote model dir
echo "Creating remote directory: ${REMOTE_MODEL_DIR}"
if [[ "$LOCAL_MODE" == true ]]; then
  run_local bash -lc "mkdir -p ${REMOTE_MODEL_DIR} && chmod 755 ${REMOTE_MODEL_DIR}"
else
  run_remote bash -lc "mkdir -p ${REMOTE_MODEL_DIR} && chmod 755 ${REMOTE_MODEL_DIR}"
fi

# If target exists and not forcing, abort
if [[ "$DRY_RUN" == false ]]; then
  if ssh "${SSH_TARGET}" "${SSH_OPTS[@]}" -- test -f "${REMOTE_TARGET_PATH}" >/dev/null 2>&1; then
    if [[ "$FORCE" != true ]]; then
      echo "Remote model already exists at ${REMOTE_TARGET_PATH}. Use --force to overwrite. Aborting."
      exit 3
    else
      echo "Overwriting existing remote model (forced)"
    fi
  fi
fi

# Copy or move the remote file into place
# We will copy to preserve original
echo "Copying model file ${REMOTE_FILE} to ${REMOTE_TARGET_PATH} (copy, not move)"
if [[ "$LOCAL_MODE" == true ]]; then
  run_local bash -lc "cp -v ${REMOTE_FILE} ${REMOTE_TARGET_PATH} && chmod 644 ${REMOTE_TARGET_PATH}"
else
  run_remote bash -lc "cp -v ${REMOTE_FILE} ${REMOTE_TARGET_PATH} && chmod 644 ${REMOTE_TARGET_PATH}"
fi

# Optionally create/update atomic symlink (point a friendly name at this model dir)
if [[ -n "${SYMLINK_NAME}" ]]; then
  SYMLINK_PATH="~/.ollama/models/${SYMLINK_NAME}"
  echo "Creating/atomically switching symlink ${SYMLINK_PATH} -> ${REMOTE_MODEL_DIR}"
  # Use -sfn for atomic update
  if [[ "$LOCAL_MODE" == true ]]; then
    run_local bash -lc "ln -sfn ${REMOTE_MODEL_DIR} ${SYMLINK_PATH} && echo 'Symlink created: ${SYMLINK_PATH} -> ${REMOTE_MODEL_DIR}'"
  else
    run_remote bash -lc "ln -sfn ${REMOTE_MODEL_DIR} ${SYMLINK_PATH} && echo 'Symlink created: ${SYMLINK_PATH} -> ${REMOTE_MODEL_DIR}'"
  fi
fi

# Optional: register the model with Ollama by creating a Modelfile and running 'ollama create'
REGISTER=false
CREATE_ASYNC=false
CREATE_TIMEOUT=0
QUANTIZE=""


# Verify ollama lists the model (best-effort)
echo "Checking ollama model list on remote..."
if [[ "$DRY_RUN" == false ]]; then
  # List models and try to detect model name
  if [[ "$LOCAL_MODE" == true ]]; then
    if command -v ollama >/dev/null 2>&1; then
      echo "Ollama is installed; listing models:"
      ollama models || true
      echo "If the model does not appear in the list, you can run with --register to create a Modelfile and register it with Ollama."
    else
      echo "Ollama not found locally; placed GGUF at ${REMOTE_TARGET_PATH}, but Ollama is not available to verify."
    fi
  else
    if ssh "${SSH_TARGET}" "${SSH_OPTS[@]}" -- command -v ollama >/dev/null 2>&1; then
      echo "Ollama is installed; listing models:"
      ssh "${SSH_TARGET}" "${SSH_OPTS[@]}" -- ollama models || true
      echo "If the model does not appear in the list, you can run with --register to create a Modelfile and register it with Ollama."
    else
      echo "Ollama not found on remote; placed GGUF at ${REMOTE_TARGET_PATH}, but Ollama is not available to verify."
    fi
  fi
fi

# Optionally register/create the model in Ollama using a Modelfile
if [[ "$REGISTER" == true ]]; then
  if [[ "$DRY_RUN" == true ]]; then
    echo "DRY RUN: would register model ${MODEL_NAME} with Ollama (would write Modelfile pointing at ${REMOTE_MODEL_DIR})"
  else
    echo "Registering model '${MODEL_NAME}' with Ollama via Modelfile pointing at ${REMOTE_MODEL_DIR}"

    MODFILE_CONTENT="FROM ${REMOTE_MODEL_DIR}"
    MODFILE_REMOTE="/tmp/Modelfile.${MODEL_NAME}"
    CREATE_LOG_REMOTE="/tmp/install_ollama_model_${MODEL_NAME}.create.log"
    CREATE_PID_REMOTE="/tmp/install_ollama_model_${MODEL_NAME}.create.pid"

    # Build the create command args
    CREATE_CMD=(ollama create "${MODEL_NAME}" -f "${MODFILE_REMOTE}")
    if [[ -n "${QUANTIZE}" ]]; then
      CREATE_CMD+=( -q "${QUANTIZE}" )
    fi

    # Check if model already exists
    MODEL_EXISTS=false
    if [[ "$LOCAL_MODE" == true ]]; then
      if command -v ollama >/dev/null 2>&1 && ollama list | grep -E "^${MODEL_NAME}[: ]" >/dev/null 2>&1; then
        MODEL_EXISTS=true
      fi
    else
      if ssh "${SSH_TARGET}" "${SSH_OPTS[@]}" -- command -v ollama >/dev/null 2>&1 && ssh "${SSH_TARGET}" "${SSH_OPTS[@]}" -- ollama list | grep -E "^${MODEL_NAME}[: ]" >/dev/null 2>&1; then
        MODEL_EXISTS=true
      fi
    fi

    if [[ "$MODEL_EXISTS" == true && "$FORCE" != true ]]; then
      echo "Model ${MODEL_NAME} already registered in Ollama; skipping create. Use --force to force re-create."
    else
      if [[ "$LOCAL_MODE" == true ]]; then
        echo "Writing Modelfile to ${MODFILE_REMOTE} (local)"
        bash -lc "cat > ${MODFILE_REMOTE} <<EOF
${MODFILE_CONTENT}
EOF"

        if [[ "$CREATE_ASYNC" == true ]]; then
          echo "Starting async create locally: ${CREATE_CMD[*]} (logs: ${CREATE_LOG_REMOTE})"
          nohup bash -lc "${CREATE_CMD[*]}" > "${CREATE_LOG_REMOTE}" 2>&1 & echo $! > "${CREATE_PID_REMOTE}"
          echo "Create started (async); PID stored in ${CREATE_PID_REMOTE}; check ${CREATE_LOG_REMOTE} for progress."
        else
          if [[ "${CREATE_TIMEOUT}" =~ ^[0-9]+$ ]]; then
            if [[ "${CREATE_TIMEOUT}" -gt 0 ]] && command -v timeout >/dev/null 2>&1; then
              echo "Running create with timeout ${CREATE_TIMEOUT}s"
              timeout ${CREATE_TIMEOUT}s bash -lc "${CREATE_CMD[*]}" 2>&1 | tee "${CREATE_LOG_REMOTE}"
            else
              echo "Running create (this may take a long time)"
              bash -lc "${CREATE_CMD[*]}" 2>&1 | tee "${CREATE_LOG_REMOTE}"
            fi
          else
            echo "Running create (this may take a long time)"
            bash -lc "${CREATE_CMD[*]}" 2>&1 | tee "${CREATE_LOG_REMOTE}"
          fi
        fi
      else
        echo "Writing Modelfile to ${MODFILE_REMOTE} on remote host"
        run_remote bash -lc "cat > ${MODFILE_REMOTE} <<'EOF'
${MODFILE_CONTENT}
EOF"

        if [[ "$CREATE_ASYNC" == true ]]; then
          echo "Starting async create on remote"
          run_remote bash -lc "nohup ${CREATE_CMD[*]} > ${CREATE_LOG_REMOTE} 2>&1 & echo \$! > ${CREATE_PID_REMOTE} && echo 'Create started (async) on remote; PID in ${CREATE_PID_REMOTE}; log: ${CREATE_LOG_REMOTE}'"
        else
          if [[ "${CREATE_TIMEOUT}" =~ ^[0-9]+$ && "${CREATE_TIMEOUT}" -gt 0 ]] && ssh "${SSH_TARGET}" "${SSH_OPTS[@]}" -- command -v timeout >/dev/null 2>&1; then
            run_remote bash -lc "timeout ${CREATE_TIMEOUT}s ${CREATE_CMD[*]} 2>&1 | tee ${CREATE_LOG_REMOTE}"
          else
            echo "Remote system has no 'timeout' or no CREATE_TIMEOUT; running create without timeout (may block)"
            run_remote bash -lc "${CREATE_CMD[*]} 2>&1 | tee ${CREATE_LOG_REMOTE}"
          fi
        fi
      fi
    fi
  fi
fi

# Optional quick sanity check via Ollama (best-effort). Can be slow; use --sanity-check to enable.
if [[ "$SANITY_CHECK" == true ]]; then
  CHECK_NAME="${SYMLINK_NAME:-$MODEL_NAME}"
  echo "Running quick sanity check: ollama run ${CHECK_NAME} (timeout ${SANITY_TIMEOUT}s)"
  if [[ "$DRY_RUN" == false ]]; then
    if [[ "$LOCAL_MODE" == true ]]; then
      # Local: use timeout if available
      if command -v timeout >/dev/null 2>&1; then
        bash -lc "echo '${SANITY_PROMPT}' | timeout ${SANITY_TIMEOUT}s ollama run ${CHECK_NAME} >/dev/null 2>&1"
        RC=$?
      else
        bash -lc "echo '${SANITY_PROMPT}' | ollama run ${CHECK_NAME} >/dev/null 2>&1"
        RC=$?
      fi
    else
      # Remote via ssh
      if ssh "${SSH_TARGET}" "${SSH_OPTS[@]}" -- command -v timeout >/dev/null 2>&1; then
        ssh "${SSH_TARGET}" "${SSH_OPTS[@]}" -- bash -lc "echo '${SANITY_PROMPT}' | timeout ${SANITY_TIMEOUT}s ollama run ${CHECK_NAME} >/dev/null 2>&1"
        RC=$?
      else
        ssh "${SSH_TARGET}" "${SSH_OPTS[@]}" -- bash -lc "echo '${SANITY_PROMPT}' | ollama run ${CHECK_NAME} >/dev/null 2>&1"
        RC=$?
      fi
    fi

    if [[ $RC -eq 0 ]]; then
      echo "Sanity check passed for model ${CHECK_NAME}"
    else
      echo "Sanity check failed (exit $RC) for model ${CHECK_NAME}; model may be loading or require more time."
      if [[ "$LOCAL_MODE" == true ]]; then
        echo "You can retry locally: echo '${SANITY_PROMPT}' | ollama run ${CHECK_NAME}"
      else
        echo "You can retry via ssh: ssh ${SSH_TARGET} 'echo "${SANITY_PROMPT}" | ollama run ${CHECK_NAME}'"
      fi
    fi
  fi
fi

echo "Done. Model file placed at ${REMOTE_TARGET_PATH} on ${SSH_TARGET}."
if [[ "$DRY_RUN" == false ]]; then
  echo "Remote model directory listing:"
  ssh "${SSH_TARGET}" "${SSH_OPTS[@]}" -- ls -l "${REMOTE_MODEL_DIR}" || true
fi

exit 0
