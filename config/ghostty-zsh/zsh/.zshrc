# Developer shell. Environment setup lives in .zshenv.
[[ -o interactive ]] || return

HISTFILE="$HOME/.zsh_history"
HISTSIZE=100000
SAVEHIST=100000
setopt EXTENDED_HISTORY APPEND_HISTORY SHARE_HISTORY
setopt HIST_IGNORE_DUPS HIST_FIND_NO_DUPS HIST_SAVE_NO_DUPS
setopt HIST_IGNORE_SPACE HIST_REDUCE_BLANKS HIST_EXPIRE_DUPS_FIRST

# A plain fallback also works in dumb terminals and command-runner sessions.
[[ -n ${_DEV_SHELL_INTERACTIVE_INITIALIZED:-} ]] && return
PROMPT='%~ %# '
[[ -t 0 && -t 1 && ${TERM:-dumb} != dumb ]] || return
typeset -g _DEV_SHELL_INTERACTIVE_INITIALIZED=1

# Native completion first; never prompt about insecure completion directories.
typeset -gU fpath
[[ -d /opt/homebrew/share/zsh/site-functions ]] && fpath=(/opt/homebrew/share/zsh/site-functions "${fpath[@]}")
if [[ -n ${GHOSTTY_RESOURCES_DIR:-} && -d "$GHOSTTY_RESOURCES_DIR/../zsh/site-functions" ]]; then
  fpath=("$GHOSTTY_RESOURCES_DIR/../zsh/site-functions" "${fpath[@]}")
fi
typeset _dev_shell_cache="${XDG_CACHE_HOME:-$HOME/.cache}/zsh"
if [[ ! -d "$_dev_shell_cache" ]]; then
  (umask 077; command mkdir -p -- "$_dev_shell_cache") 2>/dev/null
fi
autoload -Uz compinit
if [[ -d "$_dev_shell_cache" && -w "$_dev_shell_cache" ]]; then
  compinit -i -d "$_dev_shell_cache/zcompdump-$ZSH_VERSION"
else
  compinit -i -D
fi
unset _dev_shell_cache
zmodload zsh/complist
zstyle ':completion:*' menu select
zstyle ':completion:*' matcher-list 'm:{a-zA-Z}={A-Za-z}'
zstyle ':completion:*' list-colors 'di=34' 'ln=36' 'ex=32'

bindkey -e
bindkey '^[[H' beginning-of-line
bindkey '^[[F' end-of-line
bindkey '^[[1;3C' forward-word
bindkey '^[[1;3D' backward-word

# Fuzzy history, files, and directories. fd respects project ignore files.
if (( $+commands[fzf] )); then
  if [[ -z ${FZF_DEFAULT_OPTS:-} ]]; then
    export FZF_DEFAULT_OPTS="--height=45% --layout=reverse --border --color=bg:#282c34,bg+:#3f4451,fg:#abb2bf,fg+:#d7dae0,hl:#4aa5f0,hl+:#4dc4ff,prompt:#c162de,pointer:#e05561,marker:#8cc265,spinner:#42b3c2,info:#d18f52,border:#4f5666"
  fi
  if (( $+commands[fd] )); then
    export FZF_DEFAULT_COMMAND='fd --type f --hidden --exclude .git'
    export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"
    export FZF_ALT_C_COMMAND='fd --type d --hidden --exclude .git'
  fi
  if (( $+commands[bat] )) && [[ -z ${FZF_CTRL_T_OPTS:-} ]]; then
    export FZF_CTRL_T_OPTS="--preview='bat --color=always --theme=ansi --style=numbers --line-range=:200 --paging=never -- {}' --preview-window=right:55%:hidden --bind=ctrl-/:toggle-preview"
  fi
  source <(fzf --zsh)
fi

if (( $+commands[zoxide] )); then
  eval "$(zoxide init zsh)"
fi

if (( $+commands[eza] )); then
  alias ll='eza --long --all --header --group-directories-first --icons=never'
  alias lt='eza --tree --level=2 --group-directories-first --icons=never'
fi

# Suggestions only consult local command history.
ZSH_AUTOSUGGEST_STRATEGY=(history)
ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE='fg=#737c8d'
ZSH_AUTOSUGGEST_BUFFER_MAX_SIZE=1000
[[ -r /opt/homebrew/share/zsh-autosuggestions/zsh-autosuggestions.zsh ]] &&
  source /opt/homebrew/share/zsh-autosuggestions/zsh-autosuggestions.zsh

if (( $+commands[starship] )); then
  eval "$(starship init zsh)"
else
  PROMPT='%F{blue}%~%f'$'\n''%(?.%F{green}.%F{red})>%f '
fi

# Syntax highlighting must be the final widget/plugin initialization.
if [[ -r /opt/homebrew/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh ]]; then
  source /opt/homebrew/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
  ZSH_HIGHLIGHT_STYLES[command]='fg=#8cc265'
  ZSH_HIGHLIGHT_STYLES[builtin]='fg=#8cc265'
  ZSH_HIGHLIGHT_STYLES[alias]='fg=#8cc265'
  ZSH_HIGHLIGHT_STYLES[unknown-token]='fg=#e05561,bold'
  ZSH_HIGHLIGHT_STYLES[single-quoted-argument]='fg=#d18f52'
  ZSH_HIGHLIGHT_STYLES[double-quoted-argument]='fg=#d18f52'
fi
