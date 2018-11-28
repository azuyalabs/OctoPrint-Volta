# OctoVolta
***Caution! This plugin is still at an early stage of development (alpha). Things may break...***

OctoVolta allows you to pair your OctoPrint connected 3D Printer with the Volta Dashboard. Volta Dashboard is a realtime online dashboard that shows you the current status of all of your print-job/printers live. All in one easy overview; with other handy information as well.

Volta Dashboard is currently a (working) prototype and it consists of 15 tiles (5 x 3 grid) that each can hold a widget. Widgets that have been created so far are:

* OctoPrint: Shows the current status of your printjob/printer (this works by means this OctoVolta plugin) 
* Slicer Releases: Displays the latest release versions of the major slicers
* Firmware Releases: Displays the latest release versions of the most common 3D printer firmwares
* Holidays: Upcoming holidays (in case I need to prepare printing some seasonal gifts/toys)
* Current weather: Just for fun :)
* Clock: Well, what would we be doing without the time...

Follow the steps below on how to install and configure the plugin. If you have more than one OctoPrint connected 3D Printer, just repeat the steps for each OctoPrint installation.

## How to Install
Simply download the [latest release](https://github.com/azuyalabs/OctoPrint-Volta/releases/latest) and install it using the OctoPrint Plugin Manager.

**Note**: _Installation via the bundled Plugin Manager is not available yet. Once the plugin has become stable enough, the plugin will be listed in the official OctoPrint Plugin Repository._


## Configuration
The only thing needed is a Volta API Token. In order to obtain this token, you need a Volta account. Go to [http://volta.azuya.studio](http://volta.azuya.studio) and [login](http://volta.azuya.studio/login), or if you don't have an account yet, [create](http://volta.azuya.studio/register) one first.

Once you have logged in successfully, you can find your API Token in your Volta profile (Menu under your logged in name). Copy the API Token from your Volta account and paste it in the API Token field of your OctoPrint installation (in the Volta Tab of the OctoPrint Settings).

 If you have more than one OctoPrint connected 3D Printer, just copy the same Volta API token for each of your OctoPrint installation.
 
 That is all there is! Your OctoPrint installation is now ready for the Volta Dashboard.