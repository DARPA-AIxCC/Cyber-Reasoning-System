#! /bin/bash
echo "Healing-Touch"
echo "Start pre-deployment of configuration"

./aixcc-reader --template-path=/usr/src/aixcc-apps/cerberus_configuration/cerberus.template --default-config=/usr/src/aixcc-apps/cerberus_configuration/defaults.ini &

./aixcc_status_server