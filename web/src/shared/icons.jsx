const paths = {
  activity: <><path d="M3 12h4l3-8 4 16 3-8h4" /></>,
  shield: <><path d="M12 3 20 6v5c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V6l8-3Z" /><path d="m9 12 2 2 4-4" /></>,
  smartphone: <><rect x="6" y="2.5" width="12" height="19" rx="2" /><path d="M10 18.5h4" /></>,
  search: <><circle cx="10.8" cy="10.8" r="6.6" /><path d="m16 16 4.5 4.5" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42" /></>,
  moon: <><path d="M20.5 14A8.5 8.5 0 0 1 10 3.5 8.5 8.5 0 1 0 20.5 14Z" /></>,
  chevron: <><path d="m9 18 6-6-6-6" /></>,
  command: <><path d="M9 9V6a2.5 2.5 0 1 0-2.5 2.5H9Zm0 0h6m0 0h2.5A2.5 2.5 0 1 0 15 6v3Zm0 0v6m0 0v2.5a2.5 2.5 0 1 0 2.5-2.5H15Zm0 0H9m0 0H6.5A2.5 2.5 0 1 0 9 18v-3Zm0 0V9" /></>,
  close: <><path d="m6 6 12 12M18 6 6 18" /></>,
  logout: <><path d="M10 17l5-5-5-5m5 5H3" /><path d="M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6" /></>,
  play: <><path d="m8 5 11 7-11 7z" /></>,
  layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m3 12 9 5 9-5M3 16l9 5 9-5" /></>,
  network: <><circle cx="12" cy="5" r="2.5" /><circle cx="5" cy="18" r="2.5" /><circle cx="19" cy="18" r="2.5" /><path d="m10.7 7.2-4.4 8.6m7-8.6 4.4 8.6M7.5 18h9" /></>,
  server: <><rect x="3" y="4" width="18" height="7" rx="1.5" /><rect x="3" y="13" width="18" height="7" rx="1.5" /><path d="M7 7.5h.01M7 16.5h.01M11 7.5h6M11 16.5h6" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  sliders: <><path d="M4 7h9m4 0h3M4 17h3m4 0h9" /><circle cx="15" cy="7" r="2" /><circle cx="9" cy="17" r="2" /></>,
}

export function Icon({ name, size = 20, strokeWidth = 1.7, className = '' }) {
  return (
    <svg
      className={className || undefined}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {paths[name] || paths.activity}
    </svg>
  )
}
