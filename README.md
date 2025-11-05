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

1.  Go to **Settings > Devices & Services**.
2.  Click **Add Integration** and search for "Pushover Listener".
3.  Enter your Pushover account credentials:
    * **Email:** Your Pushover account email.
    * **Password:** Your Pushover account password.
    * **Device Name:** A unique name for this listener *as it will appear in your Pushover account* (e.g., "homeassistant"). This integration will register itself with Pushover as a new device with this name.

## Usage
When a push notification is received, the integration fires a `pushover_event` on the Home Assistant event bus. The event data includes all fields from the Pushover message, plus any key-value pairs found in the message body. The last message information is stored in a sensor with the part of the name based on the device name you entered during the configuration

### Key-Value Pair Parsing
If your Pushover message body contains lines in the format `key=value`, each pair will be parsed and added as a separate field in the event data. This makes it easy to trigger automations based on structured data sent via Pushover.
Create an pushover event with the following data:

```
type=alert
message=Garage door open
```

The resulting Home Assistant event will include:

```json
{
  "id": "123456",
  "title": "Alert",
  "message": "type=alert\nlevel=critical\nmessage=Garage door open",
  "type": "alert",
  "priority": "priority_critical",
  "message": "Garage door open"
  "app": "BlueIris"
}
```

Two examples: One using the event bus the other using an the pushover device type.

#### Example 1: Sending a Message with Key-Value Pairs (key off the event bus)
Send a message from the Pushover app or API with the following body:

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
            Priority: {{ trigger.event.data.level }}
            Details: {{ trigger.event.data.message }}
```
#### Example 2: Trigger on Priority + Condition on App

This automation triggers on any critical message, but only continues if the message was sent by the "BlueIris" application.

```yaml
automation:
  - alias: "Pushover - Critical Alert from BlueIris"
    
    # 1. THE TRIGGER (User-Friendly)
    # This is selected from the UI dropdowns.
    trigger:
      - platform: device
        device_id: "a1b2c3d4e5f6..." # This is filled in by the UI
        domain: "pushover_listener"
        type: "priority_critical"

    # 2. THE CONDITION
    # Use a template condition to check any other field from the message.
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.app == 'BlueIris' }}"
    
    # 3. THE ACTION
    action:
      - service: notify.persistent_notification
        data:
          title: "BlueIris Alert!"
          message: "{{ trigger.event.data.message }}"
```


#### Example: Example: "Is the Alarm Armed?"


This automation triggers on any critical message, but only continues if the message was sent by the "BlueIris" application.

Let's imagine you have a script that sends a Pushover message from an app named "AlarmPanel" when you arm your system. The sensor will store this.

We can now build an automation that triggers on a motion sensor, but only if the last Pushover message for kevinHA1 was from the "AlarmPanel" app.

This automation answers the question: "Did I get motion while the alarm was armed?"

```yaml

automation:
  - alias: "Pushover - Sound Alarm on Motion when Armed"
    
    # 1. THE TRIGGER: Something *else* happens in Home Assistant
    trigger:
      - platform: state
        entity_id: binary_sensor.living_room_motion
        to: "on"
        
    # 2. THE CONDITION: Use the new sensor to check the last message
    condition:
      - condition: state
        # We check the sensor for the 'yourDevice' device
        entity_id: sensor.pushover_yourDevice_last_message
        # We check the 'app' attribute
        attribute: "app" 
        # We check if that attribute matches "AlarmPanel"
        state: "AlarmPanel"
        
    # 3. THE ACTION: Only runs if the trigger and condition are met
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.siren
      - service: notify.persistent_notification
        data:
          title: "ALARM TRIGGERED"
          # We can even pull the message text from the sensor!
          message: "Motion detected while alarm was armed. Last message: {{ state_attr('sensor.pushover_yourDevice_last_message', 'message') }}"


## Security & Privacy
- Do **not** share your Pushover credentials with others.
- Credentials are used only for device registration and are not stored after setup.
- No sensitive data is logged.

## Troubleshooting
- Ensure your Home Assistant instance has internet access.
- Check the Home Assistant logs for errors related to `pushover_listener`.


## License
This integration is not affiliated with or endorsed by Pushover. Use at your own risk.