#! /bin/bash

printf "Starting Healing Touch Orchestrator Instance\n"
python3 /app/orchestrator/server.py &

name="$(hostname)-{$RANDOM}"

until curl "${HEALING_TOUCH_BACKEND}/health/" >/dev/null; do
	printf "Waiting for the Backend to be available...\n"
	sleep 5
	((c++)) && ((c == 12)) && exit 1 #TODO change to failsafe instead of exit
done

printf "Run health check before we get started.\n\n"
(
	set -x
	curl "${HEALING_TOUCH_BACKEND}/health/"
) | jq


printf "Get next subject to work on.\n\n"

has_subject(){
  # Execute the curl command and store the result
  local response=$(curl "${HEALING_TOUCH_BACKEND}/has_subject/")
    # Check if the curl command was successful
  if [ $? -ne 0 ]; then
    echo "Error executing curl command"
    return 1
  fi


    # Use jq to parse the JSON and extract the variables
  local variable1=$(echo "$response" | jq -r '.status')

  if [[ $variable1 == "YES" ]];
  then
    return 1
  else
    return 0;
  fi
}


cd "/app/orchestrator"

# Ensure AFLplusplus and jacoco can be used for building if needed
# cp -rf /app/AFLplusplus ${AIXCC_CRS_SCRATCH_SPACE}/AFLplusplus

export COLUMNS=800

if [[ -n "$GOOGLE_APPLICATION_CREDENTIALS" ]];
then
      # Use jq to parse the JSON and extract the variables
  export PROJECT_ID=$(jq -r '.project_id' $GOOGLE_APPLICATION_CREDENTIALS)
  export PRIVATE_KEY_ID=$(jq -r '.private_key_id' $GOOGLE_APPLICATION_CREDENTIALS)
  export PRIVATE_KEY=$(jq -r '.private_key' $GOOGLE_APPLICATION_CREDENTIALS)
  export CLIENT_EMAIL=$(jq -r '.client_email' $GOOGLE_APPLICATION_CREDENTIALS)
  export CLIENT_ID=$(jq -r '.client_id' $GOOGLE_APPLICATION_CREDENTIALS)
  export CLIENT_CERT=$(jq -r '.client_x509_cert_url' $GOOGLE_APPLICATION_CREDENTIALS)
fi



cat <<EOF > /app/orchestrator/config/api.json
{
  "openai_token": "${OPENAI_API_KEY:-sk-proj-rJ19DXcrkLNtqWnvhfDZT3BlbkFJ7iMszPYcYuGIgr299JRn}",
  "azure_token": "${AZURE_API_KEY:-f6654447b2b14ab5a5b4264c8bdff171}",
  "azure_base": "${AZURE_API_BASE:-https://aicc.openai.azure.com}",
  "anthropic_token": "${ANTHROPIC_API_KEY:-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}",
  "huggingface_token": "",
  "gemini_token": {
    "project_id": "${PROJECT_ID:-elated-capsule-422713-i4}",
    "private_key_id": "${PRIVATE_KEY_ID:-63afd70dcc401fcc15111690cf8c49502fe64d3d}",
    "private_key": "${PRIVATE_KEY:------BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCykXEMmWaqMIy0\ngh6XOyfvF2FsurTkpsvac9zwANKQC1L4yOFzogTWG+IkDFK31+30JY79AbywQ9f9\n0ivLJLWLnATRjiOnWhMuzujT3oa4zaOaruZey2WzOWz6hoq3iBvTCsHUL+v+DFQf\nw53/kpecRb13InV6/LfUP7KOFAWf7/tvQtrfSj+8QPrT5TOHP5GiM4/XLwoM+nmI\nI1f3/80LCSw9rmhwZVLtyw8s5B5GqlGMhSTjEduqM+0CKBY+wysABWFPmA7xsb2Y\n1i9KzFSMbf3pabOPlf0CRMjArrUVWciMAeb1X+EW0PK001I4Me8Sz/lb+GkRdgw1\nKfnsT3+XAgMBAAECggEAPdUyDbhSvgz4tAq4mAqCbf6tHC7cs650OW1UbIEEaJ+b\nOA2rT9SjExbtrCjePc3WFmwpAsAmu+yKLtinlHzeJn08h+nNu8XrjZJVOgQ8p2KB\ny+7TU7DfwvtYGroa76mAZQg9DQIZGEvhl2wv2k9DE3hsvoOepZs79pGl/R++wN4O\np/w+JTmPrWK050Ui4JU7MWtjJVFyYjZaP+cAMYZnxUPV7qIK/l6rMXydZTkWuAQE\n2bClTJUiY6//5OvHF66ZfZiidUGoFjH+j7o71wajJ52PHbRRD3ofI3XvxKyNz3Qz\nNdOLBto9zewh3Ip/JFxFPwJFsN1LhGFX8Hl15Nbx1QKBgQDnuKgMZjLbjyph6Odi\nFfmf1hVOiYXEu/FNb1O8NUJL7pdCbMnRnKUXSpLqgyxpE1lFSlzTT6yzJnjsSCco\nKSHsRZZJiL1B725pwZOLzx0XwXa58q7y4H8VOLfx2L7e2N3WTYFydTMtrxH622Bw\nHjQecOAe9dYOpyiXNKYGN2D24wKBgQDFRxWP9JRdyUKt5oHF8HOJyup24Qg1F8++\nCITLGDDgAMLCpke2OPXIMyQ2IJ31yv1KK6h2bWzDBge6X/+FD6BXMx043U7JJwmR\nLXEncU0DikSuyLRqYIz9u6yJLLZIV1Ir968V9TFNNJDcSGzEWDBeVp7mbaibXL0w\nfBYHL2z+vQKBgQCkJJIl9l8gWJHVOX5uZNKm/qepMpGngtqz16ChObj0wNY1H4r3\nCNeJYDIiHTlgVWxvQPXwWggj/6S4+4OBV2HIVKLZBBvMkSbNk2pJJzWcllbb8aUs\nNwrOpZbnonnSshyyqcSAp7TRL6q04KG3yi1xQtQAGnS/fHmsYocY8DGnsQKBgQCF\nA3TKZ0JSKg1Ha5A8ge+lDKgiF4CNK8zqeJvwxBLQNjMbQzo+5xDxN2pHBJ78xy0Z\nAW7Iyub2Z+51/5wtf2fA47nkSXOBtUyCEn2k9oPSyzucDb93qjnmKtAefYM6K4ZA\nFvR6faQMRlEV9c9AY6XZNdZVz8JLXrBBLKk9lwCKkQKBgFs3wJLvEPW511hMvXQk\nJjsS/gkF6AQ2dXUAUBml0FyzFbkpqfwThjf5Ch0As77SwjV33AVKMSqmE5yYjFSO\nj6WvqDhntFRLbah5jxsijQu/nG7rGpo9F5tZKFxVhzg16Uj+wCoUG9SN5BVNFy1E\nX1jc+LUkinMlKNV2yjDOlGVC\n-----END PRIVATE KEY-----\n}",
    "client_email": "${CLIENT_EMAIL:-aixcc-897@elated-capsule-422713-i4.iam.gserviceaccount.com}",
    "client_id": "${CLIENT_ID:-112635395703021710182}",
    "client_x509_cert_url": "${CLIENT_CERT:-https://www.googleapis.com/robot/v1/metadata/x509/aixcc-897%40elated-capsule-422713-i4.iam.gserviceaccount.com}"
  }
}
EOF


# Ensure that no weird behavior happens due to git repos
git config --global --add safe.directory '*'


CPU_COUNT=`nproc`


if [[ $HT_DEV_MODE == 1 ]];
then
    while true; 
    do
        echo "Sleeping for Dev mode" 
        sleep 5; 
    done
else
    while true; 
    do
        # Execute the curl command and store the result
        response=$(curl "${HEALING_TOUCH_BACKEND}/next_subject/" --header "Content-Type: application/json" --request POST --data "{\"id\":\"${name}\"}")

        # Check if the curl command was successful
        if [ $? -ne 0 ]; then
          echo "Error executing curl command"
          sleep 10
          continue
        fi

        echo "Response is $response"

        # Use jq to parse the JSON and extract the variables
        SUBJECT_NAME=$(echo "$response" | jq -r '.subject')
        BUG_ID=$(echo "$response" | jq -r '.bug_id')
        CPU_COUNT=$(echo "$response" | jq -r '.cpus')
        SUBJECT_ID=$(echo "$response" | jq -r '.subject_name')


        printf "Subject ${SUBJECT_NAME}.\n\n"
        printf "Subject DIR ${SUBJECT_ID}.\n\n"
        printf "Bug ID ${BUG_ID}.\n\n"
        printf "CPUs ${CPU_COUNT}.\n\n"
        
        # Check if jq was successful in extracting the variables
        if [ -z "$SUBJECT_NAME" ] || [ -z "$SUBJECT_ID" ] || [ -z "$BUG_ID" ] || [ -z "$CPU_COUNT" ] || [[ "$SUBJECT_NAME" == "null" ]] || [[ "$SUBJECT_ID" == "null" ]]  || [[ "$BUG_ID" == "null" ]] || [[ "$CPU_COUNT" == "null" ]] ; then
          echo "No data passed. Sleeping a little"
          sleep 10
          continue
        fi

        
        echo "Waiting for ${AIXCC_CRS_SCRATCH_SPACE}/benchmark/darpa/${SUBJECT_NAME}/${SUBJECT_ID}/.prepared"

        until [ -f "${AIXCC_CRS_SCRATCH_SPACE}/benchmark/darpa/${SUBJECT_NAME}/${SUBJECT_ID}/.prepared" ];
        do 
            ls ${AIXCC_CRS_SCRATCH_SPACE}/benchmark/darpa/${SUBJECT_NAME}/;
            echo "Sleeping for preparation"
            sleep 10;
        done

        echo "READY!"
        workflow_name="${AIXCC_CRS_SCRATCH_SPACE}/benchmark/darpa/${SUBJECT_NAME}/workflow-${BUG_ID}-$((1 + $RANDOM % 100000)).json"
        cp "${AIXCC_CRS_SCRATCH_SPACE}/benchmark/darpa/${SUBJECT_NAME}/workflow.json" ${workflow_name}

        sed -i "s/\"\\*\"/\"${BUG_ID}\"/" ${workflow_name}
        sed -i -r "s/\"cpu(s|-count)\": 6/\"cpu\1\": ${CPU_COUNT}/" ${workflow_name}

        timeout -k 5m 4h python3 -m main \
            -c $workflow_name \
            --special-meta="${AIXCC_CRS_SCRATCH_SPACE}/benchmark/darpa/${SUBJECT_NAME}/meta-data.json" &

        sleep $((1 + $RANDOM % 5))
    done
fi