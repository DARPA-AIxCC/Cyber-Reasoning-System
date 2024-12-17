sudo apt update
sudo apt install gdb make g++ unzip afl++
cd ~;git clone https://github.com/GJDuck/e9patch.git ~/e9patch; cd ~/e9patch; bash build.sh
cd ~; git clone https://github.com/GJDuck/e9afl.git ~/e9afl; cd ~/e9afl; bash build.sh
sudo ln -s ~/e9afl/e9afl /usr/local/bin/e9afl
sudo ln -s ~/e9patch/e9tool /usr/local/bin/e9tool
