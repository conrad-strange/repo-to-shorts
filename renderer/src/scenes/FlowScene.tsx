import React from 'react';
import {Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {theme} from '../styles/theme';
import type {Scene} from '../types';
import {accentOf, beatTiming, getBeats, HighlightText, SceneShell} from './sceneKit';

export const FlowScene: React.FC<{scene: Scene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const accent = accentOf(scene);
  const beats = getBeats(scene, 5);
  const nodes = (scene.visual.diagram_nodes.length ? scene.visual.diagram_nodes : beats.map((beat) => beat.text)).slice(0, 5);

  return (
    <SceneShell scene={scene} dense>
      <div style={{display: 'grid', gap: 16}}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr auto 1fr',
            gap: 14,
            alignItems: 'center',
            marginBottom: 6,
          }}
        >
          <Endpoint label="输入" value={inputLabel(nodes)} accent={accent} />
          <div style={{color: theme.muted, fontSize: 24}}>→</div>
          <Endpoint label="输出" value={outputLabel(nodes)} accent={accent} />
        </div>

        <div style={{display: 'grid', gap: 12}}>
          {nodes.map((rawNode, index) => {
            const node = parseNode(rawNode);
            const timing = beatTiming(frame, fps, scene.duration, index * 0.13);
            const active = interpolate(
              frame,
              [Math.round((index * 0.13 + 0.04) * scene.duration * fps), Math.round((index * 0.13 + 0.16) * scene.duration * fps)],
              [0, 1],
              {easing: Easing.bezier(0.16, 1, 0.3, 1), extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
            );

            return (
              <div key={`${rawNode}-${index}`} style={{display: 'grid', gridTemplateColumns: '62px 1fr', gap: 18}}>
                <div
                  style={{
                    width: 52,
                    height: 52,
                    borderRadius: 999,
                    background: active > 0.5 ? accent : 'rgba(240,246,252,0.08)',
                    color: active > 0.5 ? '#0D1117' : theme.foreground,
                    border: `1px solid ${active > 0.5 ? accent : theme.border}`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 22,
                    fontWeight: 800,
                    opacity: timing.opacity,
                    transform: `translateY(${timing.y}px)`,
                  }}
                >
                  {index + 1}
                </div>
                <div
                  style={{
                    minHeight: 94,
                    borderRadius: 8,
                    border: `1px solid ${active > 0.5 ? accent : theme.border}`,
                    background: active > 0.5 ? 'rgba(88,166,255,0.13)' : 'rgba(22,27,34,0.78)',
                    display: 'grid',
                    gridTemplateColumns: '1fr auto',
                    alignItems: 'center',
                    gap: 18,
                    padding: '18px 24px',
                    opacity: timing.opacity,
                    transform: `translateY(${timing.y}px) scale(${timing.scale})`,
                  }}
                >
                  <div>
                    <div style={{fontSize: 34, fontWeight: 760, lineHeight: 1.1}}>
                      <HighlightText text={node.title} accent={accent} />
                    </div>
                    {node.note ? (
                      <div style={{marginTop: 8, color: theme.muted, fontSize: 23, lineHeight: 1.2}}>
                        {node.note}
                      </div>
                    ) : null}
                  </div>
                  {index < nodes.length - 1 ? (
                    <div style={{color: accent, fontSize: 26, opacity: 0.9}}>→</div>
                  ) : (
                    <div style={{color: accent, fontSize: 23, fontWeight: 760}}>Done</div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </SceneShell>
  );
};

const parseNode = (raw: string) => {
  const separator = raw.includes('：') ? '：' : raw.includes(':') ? ':' : raw.includes('\n') ? '\n' : null;
  if (!separator) {
    return {title: raw, note: ''};
  }
  const [title, ...rest] = raw.split(separator);
  return {title: title.trim(), note: rest.join(separator).trim()};
};

const inputLabel = (nodes: string[]) => parseNode(nodes[0] || '输入').title;
const outputLabel = (nodes: string[]) => parseNode(nodes[nodes.length - 1] || '输出').title;

const Endpoint: React.FC<{label: string; value: string; accent: string}> = ({label, value, accent}) => (
  <div
    style={{
      borderRadius: 8,
      border: `1px solid ${theme.border}`,
      background: 'rgba(22,27,34,0.72)',
      padding: '16px 18px',
    }}
  >
    <div style={{fontSize: 19, color: theme.muted, marginBottom: 6}}>{label}</div>
    <div style={{fontSize: 25, color: accent, fontWeight: 720, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>
      {value}
    </div>
  </div>
);
