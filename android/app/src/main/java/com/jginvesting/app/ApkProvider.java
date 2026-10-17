package com.jginvesting.app;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;

import java.io.File;
import java.io.FileNotFoundException;

/** Entrega ao instalador do Android o APK baixado (cache/update/JG-Investing.apk), só leitura e só com permissão concedida. */
public class ApkProvider extends ContentProvider {
    static final String MIME = "application/vnd.android.package-archive";

    static File file(android.content.Context c) { return new File(new File(c.getCacheDir(), "update"), "JG-Investing.apk"); }
    static Uri uri(android.content.Context c) { return Uri.parse("content://" + c.getPackageName() + ".apk/JG-Investing.apk"); }

    @Override public boolean onCreate() { return true; }
    @Override public String getType(Uri u) { return MIME; }

    @Override public ParcelFileDescriptor openFile(Uri u, String mode) throws FileNotFoundException {
        if (!"JG-Investing.apk".equals(u.getLastPathSegment())) throw new FileNotFoundException();
        return ParcelFileDescriptor.open(file(getContext()), ParcelFileDescriptor.MODE_READ_ONLY);
    }

    @Override public Cursor query(Uri u, String[] p, String s, String[] a, String o) {
        File f = file(getContext());
        MatrixCursor c = new MatrixCursor(new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE});
        c.addRow(new Object[]{f.getName(), f.length()});
        return c;
    }
    @Override public Uri insert(Uri u, ContentValues v) { return null; }
    @Override public int delete(Uri u, String s, String[] a) { return 0; }
    @Override public int update(Uri u, ContentValues v, String s, String[] a) { return 0; }
}
