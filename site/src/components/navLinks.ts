// Shared top-level nav links — used by Nav, MobileNavPanel, and Footer.
export interface NavLink {
  label: string;
  href: string;
}

export const navLinks: NavLink[] = [
  { label: 'About', href: '/about' },
  { label: 'Community', href: '/community' },
  { label: 'Racing', href: '/racing' },
  { label: 'Coaches', href: '/coaches' },
  { label: 'Wax Room', href: '/wax-room' },
  { label: 'Sponsors', href: '/sponsors' },
];
