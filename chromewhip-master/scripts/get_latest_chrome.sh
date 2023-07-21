#!/bin/bash

# delete previously versions
\rm -rf dl.google.com opt

# download latest unstable, beta, & stable chrome versions
wget -mS https://dl.google.com/linux/direct/google-chrome-{unstable,beta,stable}_current_amd64.deb

# on Debian/Ubuntu based systems, `dpkg --fsys-tarfile` can also be used to extract deb file contents,
# but ar is more generic, and availalbe on all Linux variants
ar p dl.google.com/linux/direct/google-chrome-unstable_current_amd64.deb data.tar.xz | tar --xz -xvv ./opt/google/chrome-unstable/
ar p dl.google.com/linux/direct/google-chrome-beta_current_amd64.deb data.tar.xz | tar --xz -xvv ./opt/google/chrome-beta/
ar p dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb data.tar.xz | tar --xz -xvv ./opt/google/chrome/