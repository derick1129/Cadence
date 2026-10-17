import { describe, it, expect } from 'vitest';
import { tokens } from '../src/lib/tokens';

describe('Brand Design Tokens', () => {
  it('defines the approved brand colors for light mode', () => {
    expect(tokens.colors.light.bg).toBe('#FFFFFF');
    expect(tokens.colors.light.fg).toBe('#0A0A0A');
    expect(tokens.colors.light.muted).toBe('#5E5E5E');
    expect(tokens.colors.light.card).toBe('#FFFFFF');
    expect(tokens.colors.light.line).toBe('#EAEAEA');
    expect(tokens.colors.light.accent).toBe('#0A7F5E');
  });

  it('defines the approved brand colors for dark mode', () => {
    expect(tokens.colors.dark.bg).toBe('#0A0A0A');
    expect(tokens.colors.dark.fg).toBe('#EDEDED');
    expect(tokens.colors.dark.muted).toBe('#A1A1A1');
    expect(tokens.colors.dark.card).toBe('#111111');
    expect(tokens.colors.dark.line).toBe('#242424');
    expect(tokens.colors.dark.accent).toBe('#3DD9A8');
  });

  it('defines the approved font families', () => {
    expect(tokens.fonts.heading).toBe('"Bricolage Grotesque", sans-serif');
    expect(tokens.fonts.body).toBe('"Hanken Grotesk", sans-serif');
    expect(tokens.fonts.heading).toContain('Bricolage Grotesque');
    expect(tokens.fonts.body).toContain('Hanken Grotesk');
  });

  it('defines the generous spacing scale', () => {
    expect(tokens.spacing.sectionGap).toBe('160px');
    expect(tokens.spacing.cardPadding).toBe('40px');
    expect(tokens.spacing.gridGap).toBe('24px');
  });
});
