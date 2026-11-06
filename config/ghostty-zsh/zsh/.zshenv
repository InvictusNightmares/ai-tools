# Minimal environment shared by interactive shells and command runners.
# Keep this file silent: no subprocesses, terminal control, or plugin loading.
typeset -gU path

# Prefer the managed runtimes to system defaults while retaining inherited
# project/virtualenv prefixes that already precede the system directories.
typeset -a _dev_shell_runtimes=() _dev_shell_before=() _dev_shell_after=()
typeset -i _dev_shell_system_seen=0
for _dev_shell_path in /opt/homebrew/bin /opt/homebrew/sbin /opt/homebrew/opt/python@3.15/libexec/bin /opt/homebrew/opt/ruby/bin /opt/homebrew/lib/ruby/gems/4.0.0/bin; do
  [[ -d "$_dev_shell_path" ]] && _dev_shell_runtimes+=("$_dev_shell_path")
done
for _dev_shell_path in "${path[@]}"; do
  case "$_dev_shell_path" in
    /opt/homebrew/bin|/opt/homebrew/sbin|/usr/local/bin|/usr/local/sbin|/usr/bin|/bin|/usr/sbin|/sbin|/Library/Apple/usr/bin)
      _dev_shell_system_seen=1 ;;
  esac
  if (( _dev_shell_system_seen )); then
    _dev_shell_after+=("$_dev_shell_path")
  else
    _dev_shell_before+=("$_dev_shell_path")
  fi
done
path=("${_dev_shell_before[@]}" "${_dev_shell_runtimes[@]}" "${_dev_shell_after[@]}")
unset _dev_shell_runtimes _dev_shell_before _dev_shell_after _dev_shell_system_seen

for _dev_shell_path in "$HOME/.local/bin" /usr/local/bin; do
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
