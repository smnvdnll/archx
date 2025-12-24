sudo pacman -S greetd greetd-tuigreet
sudo rm -rf /etc/greetd
sudo ln -sn $HOME/archx/config/greetd /etc/greetd
sudo systemctl enable greetd.service

