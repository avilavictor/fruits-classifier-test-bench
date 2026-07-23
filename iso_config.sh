sudo bash -c 'swapoff -a 2>/dev/null; umount -l /tmp 2>/dev/null; rm -rf /tmp_sd && mkdir -p /tmp_sd && fallocate -l 2G /tmp_sd/tmp.img && mkfs.ext4 -F /tmp_sd/tmp.img && sed -i "/\/tmp/d" /etc/fstab && echo "/tmp_sd/tmp.img /tmp ext4 loop,defaults,noatime 0 0" >> /etc/fstab && mount -a && chmod 1777 /tmp'

sudo apt install -y python3-dev python3-venv git build-essential libcurl4-openssl-dev libmicrohttpd-dev

sudo ./install_tflite.sh

sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
  bookworm stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

 sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo usermod -aG docker dietpi
newgrp docker

sudo apt install dbus
sudo systemctl unmask systemd-logind
sudo systemctl start dbus systemd-logind