sudo pacman -S --noconfirm waybar
ln -sn $HOME/archx/config/waybar $HOME/.config/waybar
hyprctl dispatch exec waybar
