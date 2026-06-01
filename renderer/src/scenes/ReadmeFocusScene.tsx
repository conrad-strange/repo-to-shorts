import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {theme} from '../styles/theme';
import type {Scene} from '../types';
import {accentOf, beatTiming, getBeats, HighlightText, SceneShell} from './sceneKit';

export const ReadmeFocusScene: React.FC<{scene: Scene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const accent = accentOf(scene);
  const beats = getBeats(scene, 3);
  const card = beatTiming(frame, fps, scene.duration, 0.08);
  const scanX = interpolate(frame, [0, Math.max(1, scene.duration * fps)], [-80, 820], {
    extrapolateRight: 'clamp',
  });

  return (
    <SceneShell scene={scene} dense>
      <div
        style={{
          borderRadius: 8,
          border: `1px solid ${theme.border}`,
          background: 'rgba(22,27,34,0.9)',
          boxShadow: `0 28px 90px ${theme.shadow}`,
          padding: '0',
          opacity: card.opacity,
          overflow: 'hidden',
          transform: `translateY(${card.y}px)`,
        }}
      >
        <div
          style={{
            height: 74,
            borderBottom: `1px solid ${theme.border}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 30px',
            background: theme.panelElevated,
          }}
        >
          <div style={{display: 'flex', alignItems: 'center', gap: 14, color: theme.foreground, fontSize: 26, fontWeight: 700}}>
            <DocIcon accent={accent} />
            README.md
          </div>
          <div style={{color: theme.muted, fontSize: 22}}>内容摘要</div>
        </div>

        <div
          style={{
            position: 'relative',
            display: 'grid',
            gridTemplateColumns: '96px 1fr',
            minHeight: 514,
          }}
        >
          <div
            style={{
              borderRight: `1px solid ${theme.border}`,
              background: 'rgba(13,17,23,0.62)',
              paddingTop: 34,
              display: 'grid',
              alignContent: 'start',
              justifyItems: 'center',
              gap: 22,
            }}
          >
            <RailIcon label="R" active accent={accent} />
            <RailIcon label="M" accent={accent} />
            <RailIcon label="<>" accent={accent} mono />
          </div>

          <div style={{position: 'relative', padding: '34px 34px 38px'}}>
            <div
              style={{
                position: 'absolute',
                top: 22,
                bottom: 22,
                left: scanX,
                width: 2,
                background: accent,
                opacity: 0.22,
              }}
            />

            <div style={{display: 'grid', gap: 18}}>
              {beats.map((beat, index) => {
                const timing = beatTiming(frame, fps, scene.duration, beat.start_ratio ?? index * 0.2);
                return (
                  <div
                    key={`${beat.text}-${index}`}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '46px 1fr',
                      gap: 18,
                      alignItems: 'start',
                      opacity: timing.opacity,
                      transform: `translateY(${timing.y}px) scale(${timing.scale})`,
                    }}
                  >
                    <div
                      style={{
                        width: 42,
                        height: 42,
                        borderRadius: 8,
                        background: index === 0 ? accent : 'rgba(240,246,252,0.08)',
                        color: index === 0 ? '#0D1117' : theme.foreground,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: 22,
                        fontWeight: 760,
                      }}
                    >
                      {index + 1}
                    </div>
                    <div
                      style={{
                        borderRadius: 8,
                        border: `1px solid ${theme.border}`,
                        background: index === 0 ? 'rgba(88,166,255,0.11)' : 'rgba(22,27,34,0.76)',
                        padding: '20px 22px',
                      }}
                    >
                      <div
                        style={{
                          color: theme.muted,
                          fontSize: 19,
                          marginBottom: 7,
                        }}
                      >
                        {index === 0 ? '项目定位' : index === 1 ? 'README 摘要' : '关键亮点'}
                      </div>
                      <div
                        style={{
                          fontSize: index === 0 ? 32 : 25,
                          fontWeight: index === 0 ? 720 : 600,
                          lineHeight: 1.28,
                          wordBreak: 'break-word',
                          overflowWrap: 'anywhere',
                          whiteSpace: 'normal',
                        }}
                      >
                        <HighlightText text={beat.text} accent={accent} />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <div
              style={{
                marginTop: 24,
                height: 58,
                borderRadius: 8,
                border: `1px solid ${theme.border}`,
                display: 'flex',
                alignItems: 'center',
                gap: 14,
                padding: '0 18px',
                color: theme.muted,
                fontSize: 22,
                background: theme.panelElevated,
              }}
            >
              <span style={{width: 8, height: 8, borderRadius: 999, background: accent}} />
              README 内容来自仓库文本摘要
            </div>
          </div>
        </div>
      </div>
    </SceneShell>
  );
};

const DocIcon: React.FC<{accent: string}> = ({accent}) => (
  <div
    style={{
      width: 34,
      height: 42,
      borderRadius: 6,
      border: `2px solid ${accent}`,
      position: 'relative',
    }}
  >
    <span style={{position: 'absolute', left: 8, top: 12, width: 16, height: 2, background: accent}} />
    <span style={{position: 'absolute', left: 8, top: 21, width: 12, height: 2, background: accent}} />
  </div>
);

const RailIcon: React.FC<{label: string; accent: string; active?: boolean; mono?: boolean}> = ({
  label,
  accent,
  active = false,
  mono = false,
}) => (
  <div
    style={{
      width: 48,
      height: 48,
      borderRadius: 8,
      background: active ? accent : 'rgba(240,246,252,0.08)',
      color: active ? '#0D1117' : theme.foreground,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontSize: mono ? 16 : 21,
      fontWeight: 760,
      fontFamily: mono ? 'SFMono-Regular, Consolas, monospace' : theme.fontFamily,
    }}
  >
    {label}
  </div>
);
