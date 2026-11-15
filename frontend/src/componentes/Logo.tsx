/** Logo de Faro: un faro estilizado. */
export default function Logo({ tamano = 28 }: { tamano?: number }) {
  return (
    <svg width={tamano} height={tamano} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <rect width="32" height="32" rx="7" fill="#2a78d6" />
      <path d="M13 9h6l1.5 17h-9z" fill="#fcfcfb" />
      <path d="M12.5 13h7M12 18h8" stroke="#2a78d6" strokeWidth="1.6" />
      <path d="M14 6h4v3h-4z" fill="#eda100" />
      <path d="M19 7.5l7-3M19 7.5l7 2M13 7.5l-7-3M13 7.5l-7 2" stroke="#eda100" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}
