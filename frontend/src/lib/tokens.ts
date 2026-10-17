export const tokens = {
  colors: {
    light: {
      bg: '#FFFFFF',
      fg: '#0A0A0A',
      muted: '#5E5E5E',
      card: '#FFFFFF',
      line: '#EAEAEA',
      accent: '#0A7F5E',
    },
    dark: {
      bg: '#0A0A0A',
      fg: '#EDEDED',
      muted: '#A1A1A1',
      card: '#111111',
      line: '#242424',
      accent: '#3DD9A8',
    },
  },
  fonts: {
    heading: '"Bricolage Grotesque", sans-serif',
    body: '"Hanken Grotesk", sans-serif',
  },
  spacing: {
    sectionGap: '160px',
    cardPadding: '40px',
    gridGap: '24px',
  },
} as const;

export type Tokens = typeof tokens;
