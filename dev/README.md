## Page Interactions


### element click
- generated


![heatmap.png](assets%2Fheatmap.png)


### mouse path
Note: this is not yet implemented

#### generated example
![img.png](assets/mousemove_events_gen.png)
![img.png](assets/mouse_path_gen.png)

#### real example
- with [mouse event testing](https://www.vsynctester.com/testing/mouse.html)
- mousepad
- Windows Laptop

=> events of almost exactly 60Hz (screen-frequency)

![img.png](assets/real_mouse_path.png)

- with [getCoalescedEvents demo](https://omwnk.csb.app/)
- gets more than 60 events/sec with `getCoalescedEvents` api
- about 2-2.1 Coalesced Event per normal event

=> about. 180 events/sec

- with mousepad
![img.png](assets/events_mousepad.png)
- with mouse
![img.png](assets/events_mouse.png)


