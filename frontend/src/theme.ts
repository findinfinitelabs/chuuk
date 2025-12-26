import { createTheme } from '@mantine/core'

export const chuukTheme = createTheme({
  primaryColor: 'violet',
  colors: {
    violet: [
      '#f3edff',
      '#e0d7fa',
      '#beabf0',
      '#9a7de6',
      '#7c55de',
      '#693cd9',
      '#5f30d8',
      '#4f23c0',
      '#461eac',
      '#3b1898'
    ],
    ocean: [
      '#e6f6ff',
      '#b3e5ff',
      '#80d4ff',
      '#4dc3ff',
      '#1ab2ff',
      '#00a1ff',
      '#0090e6',
      '#0080cc',
      '#006fb3',
      '#005e99'
    ],
  },
  primaryShade: { light: 6, dark: 8 },
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Sans Emoji"',
  fontFamilyMonospace: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
  headings: {
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    fontWeight: '700',
    sizes: {
      h1: { fontSize: '2.125rem', lineHeight: '1.3', fontWeight: '700' },
      h2: { fontSize: '1.625rem', lineHeight: '1.35', fontWeight: '700' },
      h3: { fontSize: '1.375rem', lineHeight: '1.4', fontWeight: '600' },
      h4: { fontSize: '1.125rem', lineHeight: '1.45', fontWeight: '600' },
      h5: { fontSize: '1rem', lineHeight: '1.5', fontWeight: '600' },
      h6: { fontSize: '0.875rem', lineHeight: '1.5', fontWeight: '600' },
    },
  },
  defaultRadius: 'md',
  cursorType: 'pointer',
  autoContrast: true,
  luminanceThreshold: 0.3,
})
