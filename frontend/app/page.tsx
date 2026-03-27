"use client";

import {
  ConnectionState,
  Room,
  RoomEvent,
  Track,
  type RemoteTrack
} from "livekit-client";
import { startTransition, useDeferredValue, useEffect, useRef, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

type TranscriptLine = {
  id: string;
  speaker: string;
  text: string;
  final: boolean;
};

const ROOM_NAME = "reflect-demo-room";

export default function HomePage() {
  const [room, setRoom] = useState<Room | null>(null);
  const [status, setStatus] = useState("Idle");
  const [transcript, setTranscript] = useState<TranscriptLine[]>([]);
  const deferredTranscript = useDeferredValue(transcript);
  const audioContainerRef = useRef<HTMLDivElement | null>(null);
  const [historyData, setHistoryData] = useState([]);

  useEffect(() => {
    fetch('/api/history')
      .then(res => res.json())
      .then(data => setHistoryData(data))
      .catch(console.error);
  }, []);

  useEffect(() => {
    return () => {
      room?.disconnect();
    };
  }, [room]);

  async function startCall() {
    setStatus("Requesting token");

    const response = await fetch("/api/token", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ roomName: ROOM_NAME })
    });

    if (!response.ok) {
      setStatus("Unable to fetch token");
      return;
    }

    const payload = (await response.json()) as {
      token: string;
      livekitUrl: string;
      roomName: string;
    };

    const nextRoom = new Room();

    nextRoom
      .on(RoomEvent.ConnectionStateChanged, (state: ConnectionState) => {
        setStatus(state === ConnectionState.Connected ? "Connected" : state);
      })
      .on(RoomEvent.TrackSubscribed, (track: RemoteTrack) => {
        if (track.kind !== Track.Kind.Audio) {
          return;
        }
        const element = track.attach();
        element.autoplay = true;
        audioContainerRef.current?.appendChild(element);
      })
      .on(RoomEvent.TrackUnsubscribed, (track: RemoteTrack) => {
        track.detach().forEach((element) => element.remove());
      })
      .on(RoomEvent.TranscriptionReceived, (segments, participant) => {
        startTransition(() => {
          setTranscript((current) => {
            const next = [...current];
            for (const segment of segments) {
              const line: TranscriptLine = {
                id: segment.id,
                speaker: participant?.name ?? participant?.identity ?? "Reflect",
                text: segment.text,
                final: segment.final
              };
              const existingIndex = next.findIndex((item) => item.id === segment.id);
              if (existingIndex >= 0) {
                next[existingIndex] = line;
              } else {
                next.push(line);
              }
            }
            return next;
          });
        });
      });

    await nextRoom.connect(payload.livekitUrl, payload.token);
    await nextRoom.localParticipant.setMicrophoneEnabled(true);
    setRoom(nextRoom);
    setStatus(`Connected to ${payload.roomName}`);
  }

  async function endCall() {
    room?.disconnect();
    audioContainerRef.current?.replaceChildren();
    setRoom(null);
    setTranscript([]);
    setStatus("Call ended");

    // Auto-update graph to show the newly logged day
    fetch('/api/history')
      .then(res => res.json())
      .then(data => setHistoryData(data))
      .catch(console.error);
  }

  return (
    <main className="shell">
      <div className="panel">
        <section className="hero">
          <h1 className="title">Evening Reflection Tracker</h1>
          <p className="copy">
            Tap Start Call to log your day. The agent will ask for your steps, macros, and workout notes, compute comparisons from your past history, and officially record the entry into your journal.
          </p>
          {historyData.length > 0 && (
            <div style={{ width: '100%', height: 300, marginTop: 20, marginBottom: 20 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={historyData}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                  <XAxis dataKey="name" stroke="#888" fontSize={12} />
                  <YAxis yAxisId="left" stroke="#8884d8" fontSize={12} />
                  <YAxis yAxisId="right" orientation="right" stroke="#82ca9d" fontSize={12} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #333', borderRadius: '8px' }}
                    itemStyle={{ color: '#fff' }}
                  />
                  <Legend />
                  <Line yAxisId="left" type="monotone" dataKey="calories" stroke="#8884d8" name="Calories" strokeWidth={2} />
                  <Line yAxisId="right" type="monotone" dataKey="protein" stroke="#82ca9d" name="Protein (g)" strokeWidth={2} />
                  <Line yAxisId="left" type="monotone" dataKey="steps" stroke="#ffc658" name="Steps" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="controls">
            <button className="primary" onClick={startCall} disabled={Boolean(room)}>
              Start Call
            </button>
            <button className="secondary" onClick={endCall} disabled={!room}>
              End Call
            </button>
          </div>
          <div className="status">{status}</div>
          <div ref={audioContainerRef} hidden />
        </section>

        <section className="transcript">
          <div className="transcriptHeader">
            <h2 className="transcriptTitle">Live Transcript</h2>
            <div className="transcriptMeta">{deferredTranscript.length} segments</div>
          </div>
          <div className="transcriptBody">
            {deferredTranscript.length === 0 ? (
              <div className="empty">
                Start a call to review your day. For example: &quot;Today was great. I got 10,000 steps, ate 2400 calories, hit 160g of protein, and had an awesome leg day.&quot;
              </div>
            ) : (
              deferredTranscript.map((line) => (
                <article key={line.id} className={`line ${line.final ? "" : "pending"}`.trim()}>
                  <div className="speaker">{line.speaker}</div>
                  <div className="text">{line.text}</div>
                </article>
              ))
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
