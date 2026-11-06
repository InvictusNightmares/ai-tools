# Merge this block into the existing ~/.zprofile.
# Preserve all existing private environment and network settings.
# If a Homebrew shellenv line already exists, update that line instead.
if [[ -x /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv zsh)"
fi
