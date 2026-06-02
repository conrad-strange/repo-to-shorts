export const theme = {
  background: '#0D1117',
  foreground: '#F0F6FC',
  muted: '#8B949E',
  border: 'rgba(240,246,252,0.14)',
  panel: '#161B22',
  panelElevated: '#1C2128',
  accent: '#58A6FF',
  accentAlt: '#3FB950',
  grid: 'rgba(240,246,252,0.045)',
  shadow: 'rgba(0,0,0,0.36)',
  fontFamily:
    'Inter, "SF Pro Display", "PingFang SC", "Microsoft YaHei", Arial, sans-serif',
};

export const resolveAccent = (value?: string | null) => {
  if (!value || !/^#[0-9a-fA-F]{6}$/.test(value)) {
    return theme.accent;
  }
  if (['#f85149', '#ff4d4f'].includes(value.toLowerCase())) {
    return value;
  }

  const red = Number.parseInt(value.slice(1, 3), 16);
  const green = Number.parseInt(value.slice(3, 5), 16);
  const blue = Number.parseInt(value.slice(5, 7), 16);
  const luminance = red * 0.2126 + green * 0.7152 + blue * 0.0722;
  const maxChannel = Math.max(red, green, blue);
  const minChannel = Math.min(red, green, blue);
  const isNeutral = maxChannel - minChannel < 32;
  const isWarm = red > 210 && green < 165 && blue < 170;
  const isPurple = red > 130 && blue > 170 && green < 140;

  return luminance < 105 || luminance > 235 || isNeutral || isWarm || isPurple ? theme.accent : value;
};
