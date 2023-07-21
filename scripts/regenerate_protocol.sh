#!/usr/bin/env bash

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# modified by kaliiiiiiiiii | Aurin Aegerter

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
