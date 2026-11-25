import FormControlLabel from '@mui/material/FormControlLabel';
import MenuItem from '@mui/material/MenuItem';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';

export function FormTextField({ label, value, onChange, error, helperText, type = 'text', InputLabelProps, ...rest }) {
  return (
    <TextField
      fullWidth
      size="small"
      label={label}
      type={type}
      value={value ?? ''}
      onChange={onChange}
      error={Boolean(error)}
      helperText={error || helperText}
      InputLabelProps={type === 'date' || type === 'datetime-local' ? { shrink: true, ...InputLabelProps } : InputLabelProps}
      {...rest}
    />
  );
}

export function FormSelect({ label, value, onChange, options = [], error, helperText, emptyOption, ...rest }) {
  return (
    <TextField
      fullWidth
      size="small"
      select
      label={label}
      value={value ?? ''}
      onChange={onChange}
      error={Boolean(error)}
      helperText={error || helperText}
      {...rest}
    >
      {emptyOption !== undefined && <MenuItem value="">{emptyOption}</MenuItem>}
      {options.map((option) => (
        <MenuItem key={String(option.value)} value={option.value}>
          {option.label}
        </MenuItem>
      ))}
    </TextField>
  );
}

export function FormSwitch({ label, checked, onChange, ...rest }) {
  return (
    <FormControlLabel
      control={<Switch checked={Boolean(checked)} onChange={(event) => onChange(event.target.checked)} {...rest} />}
      label={label}
    />
  );
}
