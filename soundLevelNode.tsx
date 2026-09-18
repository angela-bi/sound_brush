import { useEffect, useState } from "react";
import { Handle, Position, useReactFlow } from "@xyflow/react";

type SoundLevelNodeProps = {
    id: string;
    data: {
      ws?: WebSocket | null;
      connectedToBrush?: boolean;
    };
    selected: boolean;
  };

export function SoundLevelNode({ id, data }: SoundLevelNodeProps ) {
    // const { setNodes } = useReactFlow();
    const [level, setLevel] = useState(0);

    useEffect(() => {
        let audioCtx: AudioContext | null = null;
        let analyser: AnalyserNode | null = null;
        let source: MediaStreamAudioSourceNode | null = null;
        let rafId: number;
    
        navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
          audioCtx = new AudioContext();
          analyser = audioCtx.createAnalyser();
          source = audioCtx.createMediaStreamSource(stream);
          source.connect(analyser);
    
          const buffer = new Uint8Array(analyser.fftSize);
    
          const tick = () => {
            if (audioCtx && audioCtx.state === "suspended") {
                audioCtx.resume();
            }
            analyser!.getByteTimeDomainData(buffer);
            let sum = 0;
            for (let i = 0; i < buffer.length; i++) {
              const v = (buffer[i] - 128) / 128;
              sum += v * v;
            }
            const rms = Math.sqrt(sum / buffer.length);
            //console.log('rms', rms)
            setLevel(rms);
            //console.log(level)

            //console.log('setting nodes')
            if (data.ws && data.ws.readyState === WebSocket.OPEN && data.connectedToBrush) {
                data.ws.send(
                    JSON.stringify({
                    type: "sound_level",
                    node: id,
                    level: rms,
                    })
                );
            }

            rafId = requestAnimationFrame(tick);
          };
          tick();
        });
    
        return () => {
          if (rafId) cancelAnimationFrame(rafId);
          audioCtx?.close();
          source?.disconnect();
        };
    }, [id, data.ws, data.connectedToBrush]);


    const height = Math.min(100, level * 400); // scale

    return (
    <div
        style={{
        width: 100,
        height: 50,
        border: "0.5px solid gray",
        borderRadius: 8,
        background: "white",
        display: "flex",
        // alignItems: "flex-end",
        flexDirection: "column",
        justifyContent: "left",
        padding: 10,
        color: "white",
        fontSize: 10,
        }}
    >
        <div style={{color: "black"}}>Sound Level: {Math.round(height)}</div>
        <div
            style={{
                width: `${height}%`,
                height: "40%",
                background: "gray",
                borderRadius: 4,
                transition: "height 0.1s linear fade",
            }}
        />
        {/* <span style={{ position: "absolute", top: 4 }}>{id}</span> */}

        <Handle type="target" position={Position.Left} />
        <Handle type="source" position={Position.Right} />
    </div>
    );
    }
