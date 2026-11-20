# Run in an administrator PowerShell on each Windows PC. Opens only the ports the stacks publish, on the Private profile.
# Set the Wi-Fi network to Private first: Settings, Network and internet, Wi-Fi, the network, Network profile type.
New-NetFirewallRule -DisplayName "Asali" -Direction Inbound -Protocol TCP -LocalPort 8101-8403 -Action Allow -Profile Private
Get-NetFirewallRule -DisplayName "Asali" | Format-Table DisplayName, Enabled, Direction, Action, Profile
