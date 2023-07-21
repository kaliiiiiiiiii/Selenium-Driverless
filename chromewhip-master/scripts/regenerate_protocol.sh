#!/usr/bin/env bash

rm -rf devtools-protocol
git clone --depth=1 https://github.com/ChromeDevTools/devtools-protocol.git
cd devtools-protocol
LATEST_GIT_MSG=$(git log --oneline --no-color)
CHROMEWHIP_GIT_MSG=$(cat ../../data/devtools_protocol_msg)
echo $LATEST_GIT_MSG
echo $CHROMEWHIP_GIT_MSG
if [ "$LATEST_GIT_MSG" != "$CHROMEWHIP_GIT_MSG" ]
then
  echo "devtools-protocol has been updated. Regenerating chromewhip protocol files."
  cd ../..
  jsonpatch --indent 4 scripts/devtools-protocol/json/browser_protocol.json data/browser_protocol_patch.json > data/browser_protocol.json
  jsonpatch --indent 4 scripts/devtools-protocol/json/js_protocol.json data/js_protocol_patch.json > data/js_protocol.json
  rm -rf scripts/devtools-protocol
  echo "$LATEST_GIT_MSG" > data/devtools_protocol_msg
  cd scripts
  if $(python generate_protocol.py); then
    echo "Regeneration complete!"
  else
    echo "Regeneration failed! Exiting"
    exit 1
  fi
  if $(python check_generation.py); then
    echo "Sanity check passed!"
  else
    echo "Sanity check failed! Please manually check the generated protocol files"
    exit 1
  fi
  # add all newly generated modules
  git add ../chromewhip/protocol
  git commit -a -m "$LATEST_GIT_MSG"
  # TODO: fix me so i don't push if the the variables below are not set
  # git push https://$CHROMEWHIP_BOT_USERNAME:$CHROMEWHIP_BOT_PASSWORD@github.com/chuckus/chromewhip.git
else
  echo "no changes found!"
  rm -rf scripts/devtools-protocol
fi
