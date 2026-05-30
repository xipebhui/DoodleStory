-- CreateTable
CREATE TABLE "user" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "emailVerified" BOOLEAN NOT NULL DEFAULT false,
    "image" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "session" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "expiresAt" DATETIME NOT NULL,
    "token" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "ipAddress" TEXT,
    "userAgent" TEXT,
    "userId" TEXT NOT NULL,
    CONSTRAINT "session_userId_fkey" FOREIGN KEY ("userId") REFERENCES "user" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "account" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "accountId" TEXT NOT NULL,
    "providerId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "accessToken" TEXT,
    "refreshToken" TEXT,
    "idToken" TEXT,
    "accessTokenExpiresAt" DATETIME,
    "refreshTokenExpiresAt" DATETIME,
    "scope" TEXT,
    "password" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "account_userId_fkey" FOREIGN KEY ("userId") REFERENCES "user" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "verification" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "identifier" TEXT NOT NULL,
    "value" TEXT NOT NULL,
    "expiresAt" DATETIME NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "UserProfile" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "authUserId" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "displayName" TEXT,
    "role" TEXT NOT NULL DEFAULT 'user',
    "authProviderSubject" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "UserProfile_authUserId_fkey" FOREIGN KEY ("authUserId") REFERENCES "user" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Style" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "status" TEXT NOT NULL DEFAULT 'draft',
    "generationProfileKey" TEXT,
    "stylePrompt" TEXT NOT NULL,
    "lastTestedAt" DATETIME,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "FileAsset" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "purpose" TEXT NOT NULL,
    "storageKey" TEXT NOT NULL,
    "originalFilename" TEXT,
    "contentType" TEXT NOT NULL,
    "byteSize" INTEGER NOT NULL,
    "checksumSha256" TEXT,
    "width" INTEGER,
    "height" INTEGER,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "StyleReferenceImage" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "styleId" TEXT NOT NULL,
    "assetId" TEXT NOT NULL,
    "displayOrder" INTEGER NOT NULL DEFAULT 0,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "StyleReferenceImage_styleId_fkey" FOREIGN KEY ("styleId") REFERENCES "Style" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "StyleReferenceImage_assetId_fkey" FOREIGN KEY ("assetId") REFERENCES "FileAsset" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "StyleTest" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "styleId" TEXT NOT NULL,
    "testText" TEXT NOT NULL,
    "stylePromptSnapshot" TEXT NOT NULL,
    "generationProfileKeySnapshot" TEXT,
    "composedPrompt" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'queued',
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "maxAttempts" INTEGER NOT NULL DEFAULT 3,
    "nextRunAt" DATETIME,
    "cancelRequestedAt" DATETIME,
    "startedAt" DATETIME,
    "finishedAt" DATETIME,
    "outputAssetId" TEXT,
    "providerRequestId" TEXT,
    "errorCode" TEXT,
    "errorMessage" TEXT,
    "internalErrorRef" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "StyleTest_styleId_fkey" FOREIGN KEY ("styleId") REFERENCES "Style" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "StyleTest_outputAssetId_fkey" FOREIGN KEY ("outputAssetId") REFERENCES "FileAsset" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "GenerationTask" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "ownerUserId" TEXT NOT NULL,
    "displayTitle" TEXT NOT NULL,
    "originalText" TEXT NOT NULL,
    "imageCountMode" TEXT NOT NULL,
    "requestedImageCount" INTEGER,
    "styleId" TEXT NOT NULL,
    "styleNameSnapshot" TEXT NOT NULL,
    "stylePromptSnapshot" TEXT NOT NULL,
    "generationProfileKeySnapshot" TEXT,
    "status" TEXT NOT NULL DEFAULT 'queued',
    "currentStep" TEXT,
    "progressCurrent" INTEGER NOT NULL DEFAULT 0,
    "progressTotal" INTEGER NOT NULL DEFAULT 0,
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "maxAttempts" INTEGER NOT NULL DEFAULT 3,
    "nextRunAt" DATETIME,
    "cancelRequestedAt" DATETIME,
    "startedAt" DATETIME,
    "finishedAt" DATETIME,
    "errorCode" TEXT,
    "errorMessage" TEXT,
    "internalErrorRef" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "GenerationTask_ownerUserId_fkey" FOREIGN KEY ("ownerUserId") REFERENCES "UserProfile" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "GenerationTask_styleId_fkey" FOREIGN KEY ("styleId") REFERENCES "Style" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "GenerationStep" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "taskId" TEXT NOT NULL,
    "stepName" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'queued',
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "idempotencyKey" TEXT NOT NULL,
    "startedAt" DATETIME,
    "finishedAt" DATETIME,
    "outputRef" TEXT,
    "errorCode" TEXT,
    "errorMessage" TEXT,
    "internalErrorRef" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "GenerationStep_taskId_fkey" FOREIGN KEY ("taskId") REFERENCES "GenerationTask" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "TaskPanel" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "taskId" TEXT NOT NULL,
    "panelOrder" INTEGER NOT NULL,
    "originalTextSegment" TEXT NOT NULL,
    "promptStatus" TEXT NOT NULL DEFAULT 'pending',
    "generatedPrompt" TEXT,
    "promptModelSnapshot" TEXT,
    "errorCode" TEXT,
    "errorMessage" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "TaskPanel_taskId_fkey" FOREIGN KEY ("taskId") REFERENCES "GenerationTask" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "GeneratedImage" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "taskId" TEXT NOT NULL,
    "panelId" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'queued',
    "finalPrompt" TEXT NOT NULL,
    "generationProfileKeySnapshot" TEXT,
    "assetId" TEXT,
    "providerRequestId" TEXT,
    "startedAt" DATETIME,
    "finishedAt" DATETIME,
    "errorCode" TEXT,
    "errorMessage" TEXT,
    "internalErrorRef" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "GeneratedImage_taskId_fkey" FOREIGN KEY ("taskId") REFERENCES "GenerationTask" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "GeneratedImage_panelId_fkey" FOREIGN KEY ("panelId") REFERENCES "TaskPanel" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "GeneratedImage_assetId_fkey" FOREIGN KEY ("assetId") REFERENCES "FileAsset" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "TaskDownload" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "taskId" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'queued',
    "imageCount" INTEGER NOT NULL DEFAULT 0,
    "assetId" TEXT,
    "filename" TEXT NOT NULL,
    "errorCode" TEXT,
    "errorMessage" TEXT,
    "internalErrorRef" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "TaskDownload_taskId_fkey" FOREIGN KEY ("taskId") REFERENCES "GenerationTask" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "TaskDownload_assetId_fkey" FOREIGN KEY ("assetId") REFERENCES "FileAsset" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateIndex
CREATE UNIQUE INDEX "user_email_key" ON "user"("email");

-- CreateIndex
CREATE INDEX "session_userId_idx" ON "session"("userId");

-- CreateIndex
CREATE UNIQUE INDEX "session_token_key" ON "session"("token");

-- CreateIndex
CREATE INDEX "account_userId_idx" ON "account"("userId");

-- CreateIndex
CREATE INDEX "verification_identifier_idx" ON "verification"("identifier");

-- CreateIndex
CREATE UNIQUE INDEX "UserProfile_authUserId_key" ON "UserProfile"("authUserId");

-- CreateIndex
CREATE UNIQUE INDEX "UserProfile_email_key" ON "UserProfile"("email");

-- CreateIndex
CREATE INDEX "UserProfile_role_createdAt_idx" ON "UserProfile"("role", "createdAt");

-- CreateIndex
CREATE UNIQUE INDEX "Style_name_key" ON "Style"("name");

-- CreateIndex
CREATE INDEX "Style_status_updatedAt_idx" ON "Style"("status", "updatedAt");

-- CreateIndex
CREATE INDEX "Style_generationProfileKey_idx" ON "Style"("generationProfileKey");

-- CreateIndex
CREATE UNIQUE INDEX "FileAsset_storageKey_key" ON "FileAsset"("storageKey");

-- CreateIndex
CREATE INDEX "FileAsset_purpose_createdAt_idx" ON "FileAsset"("purpose", "createdAt");

-- CreateIndex
CREATE INDEX "StyleReferenceImage_styleId_displayOrder_createdAt_idx" ON "StyleReferenceImage"("styleId", "displayOrder", "createdAt");

-- CreateIndex
CREATE UNIQUE INDEX "StyleReferenceImage_styleId_assetId_key" ON "StyleReferenceImage"("styleId", "assetId");

-- CreateIndex
CREATE INDEX "StyleTest_styleId_createdAt_idx" ON "StyleTest"("styleId", "createdAt");

-- CreateIndex
CREATE INDEX "StyleTest_status_nextRunAt_idx" ON "StyleTest"("status", "nextRunAt");

-- CreateIndex
CREATE INDEX "GenerationTask_status_nextRunAt_idx" ON "GenerationTask"("status", "nextRunAt");

-- CreateIndex
CREATE INDEX "GenerationTask_status_updatedAt_idx" ON "GenerationTask"("status", "updatedAt");

-- CreateIndex
CREATE INDEX "GenerationTask_styleId_createdAt_idx" ON "GenerationTask"("styleId", "createdAt");

-- CreateIndex
CREATE INDEX "GenerationTask_ownerUserId_createdAt_idx" ON "GenerationTask"("ownerUserId", "createdAt");

-- CreateIndex
CREATE INDEX "GenerationTask_createdAt_idx" ON "GenerationTask"("createdAt");

-- CreateIndex
CREATE UNIQUE INDEX "GenerationStep_idempotencyKey_key" ON "GenerationStep"("idempotencyKey");

-- CreateIndex
CREATE INDEX "GenerationStep_taskId_createdAt_idx" ON "GenerationStep"("taskId", "createdAt");

-- CreateIndex
CREATE INDEX "GenerationStep_status_updatedAt_idx" ON "GenerationStep"("status", "updatedAt");

-- CreateIndex
CREATE INDEX "TaskPanel_taskId_panelOrder_idx" ON "TaskPanel"("taskId", "panelOrder");

-- CreateIndex
CREATE UNIQUE INDEX "TaskPanel_taskId_panelOrder_key" ON "TaskPanel"("taskId", "panelOrder");

-- CreateIndex
CREATE UNIQUE INDEX "GeneratedImage_panelId_key" ON "GeneratedImage"("panelId");

-- CreateIndex
CREATE INDEX "GeneratedImage_taskId_createdAt_idx" ON "GeneratedImage"("taskId", "createdAt");

-- CreateIndex
CREATE INDEX "GeneratedImage_panelId_idx" ON "GeneratedImage"("panelId");

-- CreateIndex
CREATE INDEX "GeneratedImage_status_updatedAt_idx" ON "GeneratedImage"("status", "updatedAt");

-- CreateIndex
CREATE INDEX "TaskDownload_taskId_createdAt_idx" ON "TaskDownload"("taskId", "createdAt");
