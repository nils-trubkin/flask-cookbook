#!/bin/dash
# Autostart script for kiosk mode, based on @AYapejian: https://github.com/MichaIng/DietPi/issues/1737#issue-318697621

# Resolution to use for kiosk mode, should ideally match current system resolution
RES_X=$(sed -n '/^[[:blank:]]*SOFTWARE_CHROMIUM_RES_X=/{s/^[^=]*=//p;q}' /boot/dietpi.txt)
RES_Y=$(sed -n '/^[[:blank:]]*SOFTWARE_CHROMIUM_RES_Y=/{s/^[^=]*=//p;q}' /boot/dietpi.txt)

# Command line switches: https://peter.sh/experiments/chromium-command-line-switches/
# - Review and add custom flags in: /etc/chromium.d
CHROMIUM_OPTS="--kiosk --window-size=${RES_Y:-720},${RES_X:-1280} --window-position=0,0"

# If you want tablet mode, uncomment the next line.
#CHROMIUM_OPTS+=' --force-tablet-mode --tablet-ui'

# Home page
URL=$(sed -n '/^[[:blank:]]*SOFTWARE_CHROMIUM_AUTOSTART_URL=/{s/^[^=]*=//p;q}' /boot/dietpi.txt)

# RPi or Debian Chromium package
FP_CHROMIUM=$(command -v chromium-browser)
[ "$FP_CHROMIUM" ] || FP_CHROMIUM=$(command -v chromium)

# Use "startx" as non-root user to get required permissions via systemd-logind
STARTX='xinit'
[ "$USER" = 'root' ] || STARTX='startx'

#exec "$STARTX" "$FP_CHROMIUM" $CHROMIUM_OPTS "${URL:-https://dietpi.com/}"

# Custom X session script to run xrandr and Chromium
cat << EOF > /tmp/custom_xinitrc
#!/bin/bash
# Rotate the screen using xrandr
xrandr -display :0.0 --output HDMI-1 --rotate left

# Start dbus, dunst in background
eval \$(dbus-launch)
export DBUS_SESSION_BUS_ADDRESS DBUS_SESSION_BUS_PID
export DISPLAY=:0.0 && dunst &

# Start unclutter to hide the mouse cursor
/usr/bin/unclutter -root -display :0.0 -idle 1 &

# Launch Chromium
exec "$FP_CHROMIUM" $CHROMIUM_OPTS "${URL:-https://dietpi.com/}"
EOF

# Make the custom script executable
chmod +x /tmp/custom_xinitrc

# Start X server with custom script
exec "$STARTX" /tmp/custom_xinitrc
