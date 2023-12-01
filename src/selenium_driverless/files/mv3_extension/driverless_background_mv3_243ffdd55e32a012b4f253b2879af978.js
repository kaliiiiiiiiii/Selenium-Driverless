// Forcing service worker to stay alive by sending a "ping" to a port where noone is listening
// Essentially it prevents SW to fall asleep after the first 30 secs of work.

    const INTERNAL_STAYALIVE_PORT = "Whatever_Port_Name_You_Want"
    var alivePort = null;
    StayAlive();

    async function StayAlive() {
    var lastCall = Date.now();
    var wakeup = setInterval( () => {

        const now = Date.now();
        const age = now - lastCall;

        if (alivePort == null) {
            alivePort = chrome.runtime.connect({name:INTERNAL_STAYALIVE_PORT})

            alivePort.onDisconnect.addListener( (p) => {
                alivePort = null;
                if(chrome.runtime.lastError){}
            });
        }

        if (alivePort) {
            alivePort.postMessage({content: "ping"});
        }
    }, 25000);
}