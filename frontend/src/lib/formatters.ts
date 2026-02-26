/**
 * 表示用フォーマッタ
 */

/**
 * ISO 8601 日時文字列を "YYYY-MM-DD HH:mm" 形式に変換する。
 * パース失敗時は元の文字列をそのまま返す。
 */
export function formatDisplayDate(value: string | null | undefined): string {
  if (!value) return "-";
  const d = new Date(value);
  if (isNaN(d.getTime())) return value;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
