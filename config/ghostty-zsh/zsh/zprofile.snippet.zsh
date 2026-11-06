# Merge this block into the existing ~/.zprofile.
# Preserve all existing private environment and network settings.
# If a Homebrew shellenv line already exists, update that line instead.
if [[ -x /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv zsh)"
fi

# Keep an explicitly activated Python environment first after macOS path_helper
# and Homebrew have initialized a login shell.
if [[ -n ${VIRTUAL_ENV:-} && -d "$VIRTUAL_ENV/bin" ]]; then
  typeset -gU path
  path=("$VIRTUAL_ENV/bin" "${path[@]}")
  export PATH
fi
