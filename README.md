# Pushover Listener for Home Assistant

This custom integration allows Home Assistant to receive push notifications from the [Pushover Open Client API](https://pushover.net/api/open_client). It registers Home Assistant as a Pushover device and listens for incoming messages, firing events in Home Assistant for each received notification.

## Features
- Registers Home Assistant as a Pushover Open Client device
- Listens for push notifications in real time
- Fires a `pushover_event` on the Home Assistant event bus for each received message
- **Parses key-value pairs in the message body and adds them as individual event data fields**

## Installation
1. Copy the `pushover_listener` folder to your Home Assistant `custom_components` directory:
   ```sh
   cp -r pushover_listener/ /config/custom_components/
   ```
2. Restart Home Assistant.

## Configuration
Add the following to your `configuration.yaml`:

```yaml
pushover_listener:
  email: YOUR_PUSHOVER_EMAIL
  password: YOUR_PUSHOVER_PASSWORD
  # Optional: device_name (default: homeassistant)
  # device_name: my_ha_device
```

- `email`: Your Pushover account email address
- `password`: Your Pushover account password
- `device_name`: (Optional) Name for the device as it will appear in Pushover

**Note:** Your credentials are used only to register the device and obtain a session. They are not stored after registration.

## Usage
When a push notification is received, the integration fires a `pushover_event` on the Home Assistant event bus. The event data includes all fields from the Pushover message, plus any key-value pairs found in the message body.

### Key-Value Pair Parsing
If your Pushover message body contains lines in the format `key=value`, each pair will be parsed and added as a separate field in the event data. This makes it easy to trigger automations based on structured data sent via Pushover.

#### Example: Sending a Message with Key-Value Pairs
Send a message from the Pushover app or API with the following body:

```
type=alert
level=critical
message=Garage door open
```

The resulting Home Assistant event will include:

```json
{
  "id": "123456",
  "title": "Alert",
  "message": "type=alert\nlevel=critical\nmessage=Garage door open",
  "type": "alert",
  "level": "critical",
  "message": "Garage door open"
}
```

### Example Automation Using Parsed Fields
You can trigger automations based on these parsed fields:

```yaml
automation:
  - alias: Critical Alert from Pushover
    trigger:
      - platform: event
        event_type: pushover_event
        event_data:
          level: critical
    action:
      - service: notify.mobile_app_your_phone
        data:
          message: >
            Critical alert received!
            Type: {{ trigger.event.data.type }}
            Level: {{ trigger.event.data.level }}
            Details: {{ trigger.event.data.message }}
```

## Security & Privacy
- Do **not** share your Pushover credentials with others.
- Credentials are used only for device registration and are not stored after setup.
- No sensitive data is logged.

## Troubleshooting
- Ensure your Home Assistant instance has internet access.
- Check the Home Assistant logs for errors related to `pushover_listener`.
- If you change your Pushover password, you may need to remove the `.storage/pushover_listener.json` file and restart Home Assistant to re-register the device.

## License
This integration is not affiliated with or endorsed by Pushover. Use at your own risk.