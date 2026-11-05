import { useTheme } from './theme-context.jsx'

/** Uses the supplied monochrome mark that matches the active application theme. */
export default function ThemeLogo({ className = '', alt = '' }) {
  const { theme } = useTheme()
  return <img className={className || undefined} src={`/app/brand/project-logo-${theme}.svg`} alt={alt} aria-hidden={alt ? undefined : 'true'} />
}
