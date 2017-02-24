# setup loggly syslog, tell docker to use syslog
set -e

curl -O https://www.loggly.com/install/configure-linux.sh
bash configure-linux.sh -a jupyter -u jupyter

cat <<EOF >> /etc/rsyslog.d/22-loggly.conf

#Script below will send  'docker/Container ID' in appName.
if re_match(\$syslogtag,'(docker)')
then
{
    set \$!extract = re_extract(\$syslogtag,'(docker/[a-zA-Z0-9]*)',0,1,"");
    set \$!syslogtag= \$!extract;
}
else
    set \$!syslogtag = \$syslogtag;
EOF

service rsyslog restart

test -d /etc/systemd/system/docker.service.d/ || mkdir -p /etc/systemd/system/docker.service.d/
cat <<EOF > /etc/systemd/system/docker.service.d/custom.conf
[Service]
ExecStart=
ExecStart=/usr/bin/dockerd --log-driver=syslog -H fd://
EOF

systemctl daemon-reload
systemctl restart docker
