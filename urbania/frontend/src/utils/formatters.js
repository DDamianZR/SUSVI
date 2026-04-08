export const formatMXN = (val) => {
  return new Intl.NumberFormat('es-MX', { 
    style: 'currency', 
    currency: 'MXN', 
    maximumFractionDigits: 0 
  }).format(val || 0);
};
  
export const formatPercentage = (val) => {
  return typeof val === 'number' ? `${val.toFixed(1)}%` : '0.0%';
};

export const formatYears = (val) => {
  return typeof val === 'number' ? `${val.toFixed(1)} años` : '0 años';
};
