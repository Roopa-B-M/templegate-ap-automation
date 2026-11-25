import Grid from '@mui/material/Grid';
import { FormTextField } from './FormControls';

export const EMPTY_VENDOR_FORM = {
  code: '',
  name: '',
  legal_name: '',
  gstin: '',
  pan: '',
  email: '',
  phone: '',
  address_line1: '',
  address_line2: '',
  city: '',
  state: '',
  state_code: '',
  pincode: '',
};

export function validateVendorForm(form) {
  const errors = {};
  ['code', 'name', 'gstin', 'email', 'address_line1', 'city', 'state', 'state_code', 'pincode'].forEach((key) => {
    if (!String(form[key] || '').trim()) errors[key] = 'Required';
  });
  return errors;
}

/** Shared field grid for vendor create (list page) and vendor edit (detail page). */
export default function VendorFormFields({ form, setField, errors = {} }) {
  return (
    <Grid container spacing={1.5}>
      <Grid item xs={12} sm={6}>
        <FormTextField label="Vendor code *" value={form.code} onChange={(e) => setField('code', e.target.value)} error={errors.code} />
      </Grid>
      <Grid item xs={12} sm={6}>
        <FormTextField label="Name *" value={form.name} onChange={(e) => setField('name', e.target.value)} error={errors.name} />
      </Grid>
      <Grid item xs={12} sm={6}>
        <FormTextField label="Legal name" value={form.legal_name} onChange={(e) => setField('legal_name', e.target.value)} error={errors.legal_name} />
      </Grid>
      <Grid item xs={12} sm={6}>
        <FormTextField label="GSTIN *" value={form.gstin} onChange={(e) => setField('gstin', e.target.value)} error={errors.gstin} />
      </Grid>
      <Grid item xs={12} sm={6}>
        <FormTextField label="PAN" value={form.pan} onChange={(e) => setField('pan', e.target.value)} error={errors.pan} />
      </Grid>
      <Grid item xs={12} sm={6}>
        <FormTextField label="Email *" type="email" value={form.email} onChange={(e) => setField('email', e.target.value)} error={errors.email} />
      </Grid>
      <Grid item xs={12} sm={6}>
        <FormTextField label="Phone" value={form.phone} onChange={(e) => setField('phone', e.target.value)} error={errors.phone} />
      </Grid>
      <Grid item xs={12} sm={6}>
        <FormTextField label="Address line 1 *" value={form.address_line1} onChange={(e) => setField('address_line1', e.target.value)} error={errors.address_line1} />
      </Grid>
      <Grid item xs={12} sm={6}>
        <FormTextField label="Address line 2" value={form.address_line2} onChange={(e) => setField('address_line2', e.target.value)} error={errors.address_line2} />
      </Grid>
      <Grid item xs={12} sm={6}>
        <FormTextField label="City *" value={form.city} onChange={(e) => setField('city', e.target.value)} error={errors.city} />
      </Grid>
      <Grid item xs={12} sm={6}>
        <FormTextField label="State *" value={form.state} onChange={(e) => setField('state', e.target.value)} error={errors.state} />
      </Grid>
      <Grid item xs={12} sm={6}>
        <FormTextField label="State code *" value={form.state_code} onChange={(e) => setField('state_code', e.target.value)} error={errors.state_code} />
      </Grid>
      <Grid item xs={12} sm={6}>
        <FormTextField label="Pincode *" value={form.pincode} onChange={(e) => setField('pincode', e.target.value)} error={errors.pincode} />
      </Grid>
    </Grid>
  );
}
