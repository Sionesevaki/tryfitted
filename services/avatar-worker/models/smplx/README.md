# SMPL-X Model Setup Instructions

## Download SMPL-X Models

You need to download the SMPL-X model files to enable avatar generation.

### Steps:

1. **Register for SMPL-X** (free for research use)
   - Go to: https://smpl-x.is.tue.mpg.de/
   - Click "Register" and create an account
   - Accept the license agreement

2. **Download the models**
   - After registration, log in
   - Navigate to the Downloads section
   - Download the following files:
     - `SMPLX_MALE.pkl`
     - `SMPLX_FEMALE.pkl`
     - `SMPLX_NEUTRAL.pkl`

3. **Place the models in this directory**
   ```
   services/avatar-worker/models/smplx/
   ├── SMPLX_MALE.pkl
   ├── SMPLX_FEMALE.pkl
   └── SMPLX_NEUTRAL.pkl
   ```

4. **Verify the setup**
   - The worker will look for these files at startup
   - If missing, you'll see errors in the logs

## Alternative: Use Docker Volume

If deploying with Docker, you can mount the models directory:

```bash
docker run -v /path/to/smplx/models:/app/models/smplx tryfitted-avatar-worker
```

## Security Note

⚠️ **DO NOT commit these model files to git!**
- They are already in `.gitignore`
- The license prohibits redistribution
- Each user must download them individually
