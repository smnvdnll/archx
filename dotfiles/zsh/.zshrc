# zshrc
export ZSH="$HOME/.oh-my-zsh"

DISABLE_AUTO_UPDATE="true"
DISABLE_MAGIC_FUNCTIONS="true"
DISABLE_COMPFIX="true"

ZSH_COMPDUMP="$HOME/.cache/zsh/zcompdump-$ZSH_VERSION"
mkdir -p "$HOME/.cache/zsh"
# oh-my-zsh

ZSH_THEME="robbyrussell"
# oh-my-zsh plugins

plugins=(
  git
  sudo
  zsh-autosuggestions
  zsh-syntax-highlighting
)

source $ZSH/oh-my-zsh.sh

# fzf
eval "$(fzf --zsh)"

# bat
alias cat="bat"

# eza
alias ls="eza -lah"

# cd aliases
alias ..="cd .."
alias ...="cd ../.."
alias ....="cd ../../.."
alias .....="cd ../../../.."

fastfetch
