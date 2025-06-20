# Pushover Listener for Home Assistant

This custom integration allows Home Assistant to receive push notifications from the [Pushover Open Client API](https://pushover.net/api/open_client). It registers Home Assistant as a Pushover device and listens for incoming messages, firing events in Home Assistant for each received notification.

## Features
- Registers Home Assistant as a Pushover Open Client device
- Listens for push notifications in real time
- Fires a `pushover_event` on the Home Assistant event bus for each received message
- Extracts key-value pairs from the message body and includes them in the event data

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

### Example Automation
You can trigger automations based on incoming Pushover messages:

```yaml
automation:
  - alias: React to Pushover Event
    trigger:
      - platform: event
        event_type: pushover_event
    action:
      - service: notify.persistent_notification
        data:
          message: "Received Pushover message: {{ trigger.event.data.message }}"
```

### Event Data Example
A received event might look like:

```json
{
  "id": "123456",
  "title": "Alert",
  "message": "temperature=23.5\nhumidity=40",
  "temperature": "23.5",
  "humidity": "40"
}
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