import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import LinearProgress from '@mui/material/LinearProgress';
import Paper from '@mui/material/Paper';
import Skeleton from '@mui/material/Skeleton';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TablePagination from '@mui/material/TablePagination';
import TableRow from '@mui/material/TableRow';
import EmptyState from './EmptyState';
import { getApiErrorMessage } from '../utils/format';

/**
 * Server-paginated table wrapper.
 * columns: [{ id, label, align, width, render(row) }]
 */
export default function DataTable({
  columns,
  rows,
  count,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
  loading = false,
  error = null,
  onRetry,
  emptyTitle = 'No records found',
  emptySubtitle,
  minWidth = 720,
}) {
  return (
    <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
      {error && (
        <Alert
          severity="error"
          sx={{ m: 2 }}
          action={
            onRetry ? (
              <Button color="inherit" size="small" onClick={onRetry}>
                Retry
              </Button>
            ) : undefined
          }
        >
          {getApiErrorMessage(error)}
        </Alert>
      )}
      {loading && <LinearProgress sx={{ height: 2 }} />}
      <TableContainer sx={{ overflowX: 'auto' }}>
        <Table size="small" sx={{ minWidth }}>
          <TableHead>
            <TableRow>
              {columns.map((column) => (
                <TableCell key={column.id} align={column.align || 'left'} sx={{ width: column.width }}>
                  {column.label}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              Array.from({ length: 5 }).map((_row, index) => (
                <TableRow key={index}>
                  {columns.map((column) => (
                    <TableCell key={column.id}>
                      <Skeleton animation="wave" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : rows.length === 0 && !error ? (
              <TableRow>
                <TableCell colSpan={columns.length}>
                  <EmptyState title={emptyTitle} subtitle={emptySubtitle} />
                </TableCell>
              </TableRow>
            ) : (
              rows.map((row, index) => (
                <TableRow hover key={row.id ?? index}>
                  {columns.map((column) => (
                    <TableCell key={column.id} align={column.align || 'left'}>
                      {column.render ? column.render(row) : (row[column.id] ?? '—')}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
      <TablePagination
        component="div"
        count={count}
        page={page}
        rowsPerPage={pageSize}
        rowsPerPageOptions={[10, 25, 50]}
        onPageChange={(_event, newPage) => onPageChange(newPage)}
        onRowsPerPageChange={(event) => onPageSizeChange && onPageSizeChange(parseInt(event.target.value, 10))}
      />
    </Paper>
  );
}
