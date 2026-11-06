# Minimal environment shared by interactive shells and command runners.
# Keep this file silent: no subprocesses, terminal control, or plugin loading.
typeset -gU path
for _dev_shell_path in /opt/homebrew/bin /opt/homebrew/sbin "$HOME/.local/bin" /usr/local/bin; do
  [[ -d "$_dev_shell_path" ]] && path+=("$_dev_shell_path")
done

# Reuse the existing Android SDK without replacing an inherited SDK selection.
if [[ -z ${ANDROID_SDK_ROOT:-} && -d "$HOME/Library/Android/sdk" ]]; then
  export ANDROID_SDK_ROOT="$HOME/Library/Android/sdk"
fi
if [[ -n ${ANDROID_SDK_ROOT:-} ]]; then
  for _dev_shell_path in "$ANDROID_SDK_ROOT/platform-tools" "$ANDROID_SDK_ROOT/emulator" "$ANDROID_SDK_ROOT/tools" "$ANDROID_SDK_ROOT/tools/bin"; do
    [[ -d "$_dev_shell_path" ]] && path+=("$_dev_shell_path")
  done
fi
unset _dev_shell_path
export PATH
